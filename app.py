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

    # Add all input addresses as edges leading to the TXID node
    for vin in inputs:
        from_addr = vin.get('prevout', {}).get('scriptpubkey_address', 'unknown')
        G.add_edge(from_addr, txid)

    # Add all output addresses as edges going out from the TXID node
    for vout in outputs:
        to_addr = vout.get('scriptpubkey_address', 'unknown')
        G.add_edge(txid, to_addr)

    # Step 4: Draw and save the graph image
    nx.draw(G, with_labels=True, node_color='lightblue', node_size=2000, font_size=8)
    plt.tight_layout()
    plt.savefig('static/graph.png')  # Save graph to static folder
    plt.clf()  # Clear plot for future use

    # Step 5: Basic privacy score based on common privacy heuristics
    score = 100

    # Heuristic 1: More than one input → inputs likely owned by same person
    if len(inputs) > 1:
        score -= 20

    # Heuristic 2: Output address equals input address → address reuse = bad
    reused = any(
        vout.get('scriptpubkey_address') == 
        inputs[0].get('prevout', {}).get('scriptpubkey_address')
        for vout in outputs
    )
    if reused:
        score -= 30

    # Additional heuristics can be added here later...

    # Step 6: Return the result page with score and image
    return render_template('result.html', score=score, txid=txid)

# Run the Flask server
if __name__ == '__main__':
    app.run(debug=True)
