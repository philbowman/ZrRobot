import sys
import subprocess
import os
import csv

STUDENTWORK_DIR = "studentwork/"

if not os.path.exists(STUDENTWORK_DIR):
    subprocess.run("mkdir " + STUDENTWORK_DIR, shell=True)


def get_projects(slug, foldername):
    print(f"fetching student work for {slug}")
    assignment_path = STUDENTWORK_DIR + foldername

    #make the assignment folder.
    if not os.path.exists(assignment_path):
        subprocess.run("mkdir " + assignment_path, shell=True)

    #iterate over students in students.csv
    try:
        with open("students.csv") as students:
            for person in csv.DictReader(students):
                github_url = "https://github.com/me50/" + person['username']
                student_path = assignment_path + "/" + person['folder']
                
                #pull/update repos that have already been cloned
                if os.path.exists(student_path):
                    print(f"{student_path} exists; pulling...")
                    subprocess.run("git pull --rebase", shell=True, cwd=student_path)
                
                #clone repos that haven't yet been cloned
                else:
                    print(f"{student_path} doesn't exist. cloning {github_url}")
                    subprocess.run(f"git clone -b {slug} {github_url} {person['folder']}", shell=True, cwd=assignment_path)

    except FileNotFoundError:
        print("students.csv does not exist")

def get_assignments():
    try:
        #iterate over list of assignments in slugs.csv
        with open('slugs.csv') as slugs:
            for slug in csv.DictReader(slugs):
                #use user-defined local folder name
                if slug['folder']:
                    foldername = slug['folder']
                
                else:
                    slug_arr = slug['slug'].split('/')
                    #create folder names for "more" and "less" assignments
                    if slug_arr[-1] == "less" or slug_arr[-1] == "more":
                        foldername = f"{slug_arr[-2]}_{slug_arr[-1]}"
                    else:
                        foldername = slug_arr[-1]

                get_projects(slug['slug'], foldername)
    
    except FileNotFoundError:
        print("slugs.csv does not exist")

get_assignments()



