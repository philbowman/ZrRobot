## Multi-Puller ##

This script is for teachers of CS50AP.  It will let you pull all the student work for a number of assignments, into folders that you name or that are auto-generated from the slug.  

Run the script with `python3 puller.py`.

- This script does not handle authentication with GitHub. You must set up an SSH key according to the instructions [here](https://cs50.readthedocs.io/github/).
- You must create slugs.csv and students.csv. Templates are proivded in the repo.
- By default, student repos will be cloned into `[location_of_puller.py]/studentwork/[assignment folder]/[student folder]` where student_folder is defined in students.csv and assignment_folder is defined in slugs.csv OR is auto-generated from the last one term in the slug (or two terms if the last term is "more" or "less")
  - `cs50/problems/2021/fall/mario/more` becomes `mario_more` 
  - `cs50/problems/2021/fall/cash` becomes `cash`

- If a repo has already been cloned into the folder specified in students.csv, the script will pull the latest changes. 

- If a student has not turned in an assignment, puller simply does not create a folder for that assignment for that user

- Compare work with [cs50's compare tool](https://cs50.readthedocs.io/projects/compare50/en/latest/) with from the project folder wtih, for example, `compare50 studentwork/mario_more/*/*.c -o studentwork/mario_more/compare50`

This project is based on [puller by Mark Sobkowicz](https://github.com/sobko/puller)
