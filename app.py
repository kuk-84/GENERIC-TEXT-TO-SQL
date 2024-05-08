import os
from flask import Flask, render_template, request
import subprocess
import sqlite3
from train import get_result
app = Flask(__name__)

# Define the desired folder to save the CSV file
UPLOAD_FOLDER = './data_and_model'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit_data', methods=['POST'])
def submit_data():
    question = request.form['question']
    csv_file = request.files['csv_file']
    
    # Get the filename of the uploaded CSV file
    filename = csv_file.filename
    table_id="1-"+filename[0:7]
    print(table_id)
    table_name="table_"+filename[0:7]
    print(table_name)
    # Save the uploaded CSV file to the desired folder with the same name
    csv_file.save(os.path.join(UPLOAD_FOLDER, filename))
    conn = sqlite3.connect("./data_and_model/ctable.db")
    c = conn.cursor()
    c.execute("SELECT count(name) FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    if c.fetchone()[0] == 1:
        print("Table already exists. Skipping insertion.")
        conn.close()
    else:
        subprocess.run(f'python add_csv.py ctable {filename}')
    subprocess.run(f'python add_question.py {table_id} "{question}"')
    subprocess.run(f'python add_table_json.py {table_id} {table_name} {filename}')
    subprocess.run('python ./data_and_model/output_entity_ctable.py')
    subprocess.run('python train.py')
    
    pr_query, pr_ans,ctable_table = get_result()  # Access the result through the get_result function
    return render_template('result.html', query=pr_query, ans=pr_ans,table=ctable_table,table_id=table_id)
    #return render_template('result.html', query=result[0], ans=result[1])

    
    # Process the question and CSV file as needed
    
    #return "Question: {}, CSV file '{}' saved successfully!".format(question, filename)

if __name__ == '__main__':
    app.run(debug=True)
