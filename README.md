# GENERIC-TEXT-TO-SQL

Our problem statement is generating structured query language (SQL) from the generic text, with some modification in the Basic BERT Model. 
This would improve the accuracy to 3.7%  then the basic BERT Model.
The ultimate aim of this approach is to enhance the model's comprehension of the underlying data, 
thereby improving its accuracy in generating SQL queries that precisely capture the user's intent.

Two vectors are:
1. We use the matching information of the table cells and question string to construct a vector where its length is the same as the question length.
   This question vector mainly improves the performance of WHERE-VALUE inference results.
2. We use the matching information of all the table headers and the question string to construct a vector where its length
   is the same as the table headers' length.
   

![image](https://github.com/kuk-84/GENERIC-TEXT-TO-SQL/assets/89506759/0a63ba7c-ae2c-4736-9ed7-55de66ab7065)
![image](https://github.com/kuk-84/GENERIC-TEXT-TO-SQL/assets/89506759/fcd7b650-08aa-4a16-80c5-cb3839743a2a)
![image](https://github.com/kuk-84/GENERIC-TEXT-TO-SQL/assets/89506759/05059014-3230-45fc-a0ba-8e3e16a4da6a)
![image](https://github.com/kuk-84/GENERIC-TEXT-TO-SQL/assets/89506759/4f32c3a4-fe64-4151-958f-76b9beeaf6e3)
![image](https://github.com/kuk-84/GENERIC-TEXT-TO-SQL/assets/89506759/6950e18c-d3d0-4832-83d8-5c5db0397aee)
![image](https://github.com/kuk-84/GENERIC-TEXT-TO-SQL/assets/89506759/6b5f2541-1854-4f86-872c-dc7e2db1ef4b)



#### put all jsonl and csv files in data and model as well.
#### first run output_entity.py for generating train_knowledge.jsonl and dev_knowledge.jsonl and train the model by running train_only.py
#### then run app.py for testing.
                                                                                                                               
#### For reference and pretrained models and data downoad and store in data_and_model directory.
https://github.com/guotong1988/NL2SQL-RULE/tree/master?tab=readme-ov-file#motivation    
