import sys
import subprocess
import os
import csv
from pathlib import Path
from datetime import datetime
import shutil
import git
import requests
import json
from sqlalchemy.orm import Session
from models import *


STUDENTWORK_DIR = "studentwork"
COMPARE50_DIR = "compare50"
# COURSE_ID = "958"
COURSE_ID = 1872
COURSE_TITLE = "Computer Science Principles"
TOKEN = '25e0c040383247d6a9e3d2ca9c54d4e6'

class Submit50:
    studentwork_dir = STUDENTWORK_DIR
    compare50_dir = COMPARE50_DIR

    def write_to_db(self, session):
        """
        Writes the submission data to the database using SQLAlchemy.
        """

        for slug in self.data:
            problem = session.query(Problem).filter_by(slug=slug).first()
            if not problem:
                problem = Problem(slug=slug, foldername=self.make_foldername(slug), allow_delete=0)
                session.add(problem)
            else:
                problem = session.merge(Problem(id=problem.id, slug=slug, foldername=self.make_foldername(slug), allow_delete=0))
            session.commit()
            session.flush()

        for username, submissions in self.data_per_student.items():
            # Create or update Student record
            email=self.usernames.get(username, {}).get('email', '').strip()
            student = session.query(Student).filter_by(email=email).first()
            if not student:
                student = Student(username=username, email=email)
                session.add(student)
            else:
                student = session.merge(Student(id=student.id, username=username, email=email))

            session.commit()
            session.flush()

            for slug, submission_data in submissions.items():
                # Create or update Problem record
                problem = session.query(Problem).filter_by(slug=submission_data['slug']).first()
                if not problem:
                    problem = Problem(foldername=slug, slug=submission_data['slug'], autograder="submit50")
                    session.add(problem)
                else:
                    problem = session.merge(Problem(id=problem.id, foldername=slug, slug=submission_data['slug'], autograder="submit50"))
                session.commit()
                session.flush()  

                # Create or update ProblemSubmission record
                submission = session.query(ProblemSubmission).filter_by(slug=slug, github_username=submission_data['github_username']).first()
                new_submission = ProblemSubmission(
                    archive=submission_data['archive'], 
                    github_username=submission_data['github_username'], 
                    slug=slug, 
                    github_id=submission_data['github_id'], 
                    github_url=submission_data['github_url'], 
                    checks_passed=submission_data['checks_passed'], 
                    checks_run=submission_data['checks_run'], 
                    style50_score=submission_data['style50_score'], 
                    timestamp=datetime.datetime.strptime(submission_data['timestamp'], '%a, %d %b %Y %I:%M:%S%p %Z'),
                    problem_id=problem.id,  # Link to the Problem record via problem_id
                    student_id=student.id  # Link to the Problem record via problem_id
                )
                if not submission:
                    session.add(new_submission)
                else:
                    new_submission.id = submission.id
                    session.merge(new_submission)
                session.commit()
                session.flush()



            session.commit()  # Commit the transaction

            session.close()


    @classmethod
    def get_project(cls, slug, assignment_folder, name, submission, pull=True):
        print(f"fetching {name}'s work for {slug}")
        assignment_path = os.path.join(cls.studentwork_dir, assignment_folder)

        #make the assignment folder if it doesn't exist
        if not os.path.exists(assignment_path):
            subprocess.run("mkdir " + assignment_path, shell=True)

        github_url = f"https://github.com/me50/{submission['github_username']}.git"
        student_path = os.path.join(assignment_path, name)
        pull_result = None
        exists = False

        #pull/update repos that have already been cloned
        if os.path.exists(student_path):
            exists = True
            print(f"{student_path} exists")
            if pull:
                print(f"pulling...")
                pull_result = subprocess.run("git pull --rebase", shell=True, cwd=student_path)
                
        
        #clone repos that haven't yet been cloned
        else:
            print(f"{student_path} doesn't exist.")
            if pull:
                print(f"{student_path} doesn't exist. cloning {github_url}")
                print(f"git clone -b {slug} {github_url} {student_path}")
                pull_result = subprocess.run(f"git clone -b {submission['slug']} {github_url} {student_path}", shell=True, cwd=assignment_path)
    
        # Check if an error occurred during pull
        if exists or pull_result.returncode != 0:
            return os.path.abspath(student_path)
        return None

    @staticmethod
    def parse_cs50_data(data, usernames):
        d = {}
        for slug in data:
            for submission in data[slug]:
                foldername = Submit50.make_foldername(slug)
                d.setdefault(submission['github_username'], {})
                d[submission['github_username']].setdefault(foldername, {})
                d[submission['github_username']][foldername] = submission
                d[submission['github_username']][foldername]['email'] = usernames.get(submission['github_username'], {}).get('email', '').strip()
        with open('data.json', 'w') as outfile:
            json.dump(d, outfile, indent=4)

        return d

    @staticmethod
    def run_compare50(slug, assignment_path):
        archive_folder = os.path.join(assignment_path, 'archive')
        output_dir = f"{assignment_path}/{COMPARE50_DIR}"
        distro = ""
        if os.path.exists(os.path.join(assignment_path, "distro")):
            distro = " -d "+ assignment_path + "/distro/*.c"

        if os.path.exists(output_dir):
            print("archiving old compare50 output...")
            archive_dir = output_dir+"_archived_" + datetime.now().strftime("%Y%m%d")
            if os.path.exists(archive_dir):
                shutil.rmtree(archive_dir)
            os.rename(output_dir, archive_dir)

        if os.path.exists(archive_folder):
            print(f"slug: {slug}\path: {assignment_path}")
            print(f"compare50 {assignment_path}/*/*.c -a {archive_folder}/*/*.c -o {output_dir}{distro}")
            subprocess.run(f"compare50 {assignment_path}/*/*.c -a {archive_folder}/*/*.c -o {output_dir}{distro}", shell=True)
        else:
            print("no archive found")
            print(f"compare50 {assignment_path}/*/*.c -o {output_dir}{distro}")

            subprocess.run(f"compare50 {assignment_path}/*/*.c -o {output_dir}{distro}", shell=True)

    def __init__(self, courseid, token, directory, course_title=COURSE_TITLE):
        self.courseid = courseid
        self.token = token
        self.course_title = course_title

        self.studentwork_dir = directory
        
        if not os.path.exists(self.studentwork_dir):
            subprocess.run("mkdir " + self.studentwork_dir, shell=True)
        self.refresh_data()

    def refresh_data(self, pull=False, compare=True):
        self.emails = {}
        self.usernames = {}
        with open("students.csv") as students:
            for person in csv.DictReader(students):
                self.emails[person['email']] = {'username': person['username'], 'name': person['name']}
                self.usernames[person['username']] = {'email': person['email'], 'name': person['name']}
                # self.data_per_student[person['username']]['email'] = person['email']
                # self.data_per_student[person['username']]['name'] = person['name']
        self.data = self.get_submit50_data()
        if pull:
            self.pull_projects(compare=compare)

    def pull_projects(self, compare=False):
        for username in self.data_per_student:
            for slug, submission in self.data_per_student[username].items():
                print(f"fetching student work for {slug}")
                assignment_folder = self.make_foldername(slug)
                submission['repo_path'] = self.get_project(slug, assignment_folder, self.usernames[username]['email'].split('@')[0].replace(".", "_"), submission, pull=True)

        # if compare:
        #     for folder, slug in self.foldernames.items():
        #         self.run_compare50(slug, os.path.join(self.studentwork_dir, folder))
    
    def write_json(self):
        with open('data.json', 'w') as outfile:
            json.dump(self.data_per_student, outfile, indent=4)

    @staticmethod
    def parse_foldername(slug):
        slug_arr = slug.split('-')
        if slug_arr[1] == "less" or slug_arr[1] == "more":
            slug_arr = [slug_arr[1]] + [slug_arr[0]] + slug_arr[2:]
        slug_arr.reverse()
        foldername = '/'.join(slug_arr).replace('---', '-problems-main-').replace('--', '-problems-').replace('-', '/')
        return foldername

    @staticmethod
    def make_foldername(slug):
        slug_arr = slug.split('/')
        slug_arr.reverse()
        if slug_arr[0] == "less" or slug_arr[0] == "more":
            slug_arr = [slug_arr[1]] + [slug_arr[0]] + slug_arr[2:]
        foldername = '/'.join(slug_arr).replace('/', '-').replace('problems', '').replace('main', '')
        return foldername

    def get_submit50_data(self, parse=True):
        # Define the URL
        json_url = f"https://submit.cs50.io/api/courses/{self.courseid}/submissions/export"

        # Define headers for the HTTP request
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "DELETE, POST, GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Access-Control-Allow-Headers, Authorization, X-Requested-With",
            "Authorization": f"token {self.token}",
            "Content-type": "application/x-www-form-urlencoded"
        }

        # Make the HTTP request
        response = requests.get(json_url, headers=headers)

        # Check if the request was successful
        if response.status_code == 200:
            data = response.json()  # Parse the JSON response
            self.data = data
            if parse:
                self.data_per_student = self.parse_cs50_data(data, self.usernames)
            return data  # Pass the JSON data
        else:
            print(f"Error: {response.status_code} - Unable to fetch data")
            return None

# cs50data = Submit50(COURSE_ID, TOKEN, STUDENTWORK_DIR)
# cs50data.pull_projects(compare=True)
# cs50data.write_json()



