#Quick note: I will be putting comments in the code, sometimes WAY TOO MANY comments, cause I wanna make sure I remember what I did and why I did it. My notebook is full of scribbled explanations and I want to make sure my ideas are clear here.

#LIBRARIES
from flask import Flask, render_template, request  #We use Flask for the web server.
import requests                                    #We get bitcoin data from Blockstream's API: REAL transaction data, anything including addresses, general details, confirmations, block info etc. ALSO RAW TX DATA.
import networkx as nx                              #Graph building of the transaction data. Good visualization of BTC flow, transactions, etc.
import matplotlib.pyplot as plt                    #Make the graph pretty. Can save as an image.
import os                                          #To check and create file paths.

#Flask instance for the web app
app = Flask(__name__)

#Routing for the home page
@app.route('/')
def index():
    #Refers to index.html (in templates), to make the form where users can submit the ID.
    return render_template('index.html')

#We use /analyze to handle the form submission, and (surprise surprise) analyze the user submission.
@app.route('/analyze', methods=['POST'])
def analyze():
    #Get the transaction ID entered by the user
    txid = request.form['txid']

    #Let's use Blockstream API to get transaction data
    url = f'https://blockstream.info/api/tx/{txid}'
    res = requests.get(url)

    #Oops, an error! we use ts to handle errors... either on the user's side or ours. Invalid TXID or a failed fetch.
    if res.status_code != 200:
        return "Invalid TXID or failed to fetch transaction data.", 400

    #Go thru the JSON response from blockstream API
    tx = res.json()
    inputs = tx['vin']
    outputs = tx['vout']

    #Fantastic, now we can make a graph, to show the flow of BTC
    G = nx.DiGraph()

    #Treating TXID as a node, we can add all input addresses as connections going INTO the node. EDIT: a connection between nodes AKA the movement of BTC is an edge.
    input_addresses = [vin.get('prevout', {}).get('scriptpubkey_address', 'unknown') for vin in inputs]
    output_addresses = [vout.get('scriptpubkey_address', 'unknown') for vout in outputs]

    for addr in input_addresses:
        G.add_edge(addr, txid)
    for addr in output_addresses:
        G.add_edge(txid, addr)

    #Save the drawn graph image, but make it look way better!
    pos = nx.spring_layout(G, k=1.5, seed=42)  # stable layout for clarity
    plt.figure(figsize=(12, 8))  # bigger plot area
    nx.draw(G, pos, with_labels=True, node_color='skyblue', node_size=1500, font_size=7, arrows=True)
    plt.tight_layout()
    plt.savefig('static/graph.png')  #gotta save the graph in a static folder
    plt.clf()  #Clear the plot

    #Privacy Score. Starts at 100 and then gets deducted based on privacy standards. MAIN THING THAT IM TRYNA SELL HERE. everything else after this is a supplementary to this feature, or built around this feature. I hope it works.
    score = 100
    breakdown = []  #List of tuples describing each check and its impact

    #Privacy check #1: More than one input -> probably some kind of issue about multiple wallets owned by the same person.
    if len(inputs) > 1:
        score -= 20
        breakdown.append(("Multiple inputs", -20, "Likely linked wallets or merging of funds"))

    #Privacy check #2: Output address equals input address -> address reuse = bad.
    reused = any(addr in output_addresses for addr in input_addresses)
    if reused:
        score -= 30
        breakdown.append(("Address reuse", -30, "Input and output addresses overlap"))

    #Privacy check #3: Round number outputs (e.g., 0.01 BTC) are super common and easy to guess
    round_outputs = [v for v in outputs if v.get('value') in [1_000_000, 5_000_000, 10_000_000]]  # these are satoshis: 0.01, 0.05, 0.1 BTC
    if round_outputs:
        score -= 10
        breakdown.append(("Round-number outputs", -10, "Likely the payment output"))

    #Privacy check #4: Output address is the SAME as one of the inputs = you're sending change back to yourself = traceable
    for addr in output_addresses:
        if addr in input_addresses:
            score -= 20
            breakdown.append(("Change to same address", -20, "Change returned to a reused address"))
            break

    #Privacy BONUS #5: One-time change address -> no reuse = good. We'll count this if at least one output is unique.
    unique_outputs = [addr for addr in output_addresses if addr not in input_addresses]
    if len(unique_outputs) >= 1:
        score += 10
        breakdown.append(("Fresh change address", +10, "Unlinked change destination"))

    #Privacy BONUS #6: Equal outputs = CoinJoin-like structure -> hard to tell who got paid
    output_values = [v.get('value') for v in outputs]
    if len(output_values) >= 2 and len(set(output_values)) == 1:
        score += 15
        breakdown.append(("Equal outputs", +15, "Could be CoinJoin-style obfuscation"))

    #Interpret the score for human-readable rating
    if score >= 90:
        judgment = "Excellent privacy"
    elif score >= 70:
        judgment = "Moderate privacy"
    elif score >= 50:
        judgment = "Weak privacy"
    else:
        judgment = "Very poor privacy"

    #Return the result page with score, breakdown, and image
    return render_template('result.html', score=score, txid=txid, judgment=judgment, breakdown=breakdown)

#Run the Flask server
if __name__ == '__main__':
    app.run(debug=True)
