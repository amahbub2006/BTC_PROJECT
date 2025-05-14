from flask import Flask, render_template, request
import requests
import networkx as nx
import matplotlib.pyplot as plt
import os
import uuid

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    txid = request.form['txid']
    url = f'https://blockstream.info/api/tx/{txid}'
    res = requests.get(url)
    if res.status_code != 200:
        return "Invalid TXID or failed to fetch transaction data.", 400

    tx = res.json()
    inputs = tx['vin']
    outputs = tx['vout']
    input_addresses = [vin.get('prevout', {}).get('scriptpubkey_address', 'unknown') for vin in inputs]
    output_addresses = [vout.get('scriptpubkey_address', 'unknown') for vout in outputs]
    output_values = [v.get('value') for v in outputs]

    score = 100
    breakdown = []
    graph_paths = []

    def draw_graph(label, highlight_addrs=None):
        G = nx.DiGraph()
        addr_map = {}
        label_counter = 1

        def label_addr(addr, is_input):
            nonlocal label_counter
            if addr == 'unknown':
                return 'Unknown'
            if addr in addr_map:
                return addr_map[addr]
            label = "Your Wallet" if is_input and len(addr_map) == 0 else \
                    ("Your Change" if addr in input_addresses and not is_input else f"{'Wallet' if is_input else 'Recipient'} {label_counter}")
            addr_map[addr] = label
            label_counter += 1
            return label

        for addr in input_addresses:
            src = label_addr(addr, is_input=True)
            G.add_edge(src, "TX")

        for addr in output_addresses:
            dst = label_addr(addr, is_input=False)
            G.add_edge("TX", dst)

        pos = nx.spring_layout(G, k=1.5, seed=42)
        plt.figure(figsize=(10, 6))

        node_colors = []
        for node in G.nodes():
            if highlight_addrs and node in highlight_addrs:
                node_colors.append('red')
            else:
                node_colors.append('skyblue')

        nx.draw(G, pos, with_labels=True, node_color=node_colors, node_size=2500, font_size=10, arrows=True)
        filename = f'static/graph_{uuid.uuid4().hex}.png'
        plt.savefig(filename)
        plt.clf()
        graph_paths.append((label, filename))

    if len(inputs) > 1:
        score -= 20
        breakdown.append(("Multiple inputs", -20, "Likely linked wallets or merging of funds"))
        draw_graph("Multiple inputs")

    reused = any(addr in output_addresses for addr in input_addresses)
    if reused:
        score -= 30
        breakdown.append(("Address reuse", -30, "Input and output addresses overlap"))
        draw_graph("Address reuse", highlight_addrs=["Your Wallet", "Your Change"])

    round_outputs = [v for v in outputs if v.get('value') in [1_000_000, 5_000_000, 10_000_000]]
    if round_outputs:
        score -= 10
        breakdown.append(("Round-number outputs", -10, "Likely the payment output"))
        draw_graph("Round-number outputs")

    change_to_self = any(addr in input_addresses for addr in output_addresses)
    if change_to_self:
        score -= 20
        breakdown.append(("Change to same address", -20, "Change returned to a reused address"))
        draw_graph("Change to same address", highlight_addrs=["Your Wallet", "Your Change"])

    unique_outputs = [addr for addr in output_addresses if addr not in input_addresses]
    if len(unique_outputs) >= 1:
        score += 10
        breakdown.append(("Fresh change address", +10, "Unlinked change destination"))
        draw_graph("Fresh change address")

    if len(output_values) >= 2 and len(set(output_values)) == 1:
        score += 15
        breakdown.append(("Equal outputs", +15, "Could be CoinJoin-style obfuscation"))
        draw_graph("Equal outputs")

    if score >= 90:
        judgment = "Excellent privacy"
    elif score >= 70:
        judgment = "Moderate privacy"
    elif score >= 50:
        judgment = "Weak privacy"
    else:
        judgment = "Very poor privacy"

    return render_template('result.html', score=score, txid=txid, judgment=judgment,
                           breakdown=breakdown, graph_paths=graph_paths)

if __name__ == '__main__':
    app.run(debug=True)
