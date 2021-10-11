## Multi-Puller ##

This script is for teachers of CS50AP.  It will let you pull all the student folders for a list of assignments, into a folder that you name or that is auto-generated from the slug.  

- This script does not handle authentication with GitHub. You must set up an SSH key according to the instructions [here](https://cs50.readthedocs.io/github/)
- By default, student repos will be cloned into `[location_of_puller.py]/studentwork/assignment_folder/student_folder` where student_folder is defined in students.csv and assignment_folder is defined in slugs.csv OR is auto-generated from the last one or two words in the slug.
- If a repo has already been cloned into the folder specified in students.csv, the script will pull the latest changes. 

- If a student has not turned in an assignment, puller simply does not create a folder for that assignment for that user

Run the script with `python3 puller.py`.

This project is based on [puller by Mark Sobkowicz](https://github.com/sobko/puller)