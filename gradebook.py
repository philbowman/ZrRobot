
class Gradebook(GoogleAPIModel):
    register = {}
    relative_path = "/classroom/gradebook"
    path = GoogleAPIModel.path + relative_path

    @classmethod
    def get(cls, classroom:Classroom):
        return cls.register.get(classroom.filename)

    def __init__(self, classroom) -> None:
        self.grades = {}
        self.classroom = classroom
        self.csv_folderpath = f"{type(classroom).path}/_csv"
        if not os.path.exists(self.csv_folderpath):
            os.mkdir(self.csv_folderpath)
        self.cw_headings = [cw.heading() for cw in classroom.cwlist]
        for sectionname, roster in classroom.stlist.items():
            if sectionname == "no section":
                continue
            # self.make_csv(sectionname, roster)
        self.sections = {}
        self.coursework = {}
        self.submissions = {}
        self.rubrics = {}
        self.students = []
        for cw in classroom.cwlist:
            for cidid, submission in cw.submissions.items():
                self.add_submission(submission)

        type(self).register[classroom.filename] = self

    def student_report(self, student, section=None, sort_key='date'):
        report = {}
        if not section:
            sections = student.sections
        else:
            sections = {section.filename: section}
        for sectionname, section in sections.items():
            if sectionname not in self.sections:
                continue
            report[sectionname] = {}
            for submission in [v for k, v in self.submissions.items() if v.student is student]:
                report[sectionname].update(self.submission_report(submission))
            report[sectionname] = {k: v for k, v in report[sectionname].items() if type(v) is dict}
            report[sectionname] = dict(sorted(report[sectionname].items(), key=lambda x:x[1][sort_key]))
        return report
    
    def submission_report(self, submission):
        row = {submission.coursework.filename: submission.rubric.scores()}
        row['Student Num'] = submission.student.students_id
        row['Student Name'] = submission.student.lastfirst
        row[submission.coursework.filename]['date'] = submission.coursework.get_date()
        row[submission.coursework.filename]['title'] = submission.coursework.title
        row[submission.coursework.filename]['heading'] = submission.coursework.heading()
        row[submission.coursework.filename]['coursework_url'] = submission.coursework.cr['alternateLink']
        row[submission.coursework.filename]['submission_url'] = submission.cr['alternateLink']
        row[submission.coursework.filename]['rubric_url'] = submission.grade_url

        return row
    
    def section_report(self, section, sort_key='date'):
        report = {}
        for coursework in [cw for filename, cw in self.coursework.items()]:
            for submission in [v for k, v in coursework.submissions.items() if v.section is section]:
                rep = self.submission_report(submission)
                report.setdefault(rep['Student Name'], rep)
                report[rep['Student Name']].update(rep)
        report = dict(sorted(report.items(), key=lambda x:x[1][sort_key]))
        return report

    def add_section(self, section):
        self.sections[str(section)] = section

    def add_coursework(self, coursework):
        self.coursework[coursework.filename] = coursework

    def add_submission(self, submission):
        self.add_coursework(submission.coursework)
        self.add_section(submission.section)
        self.students.append(submission.student)

        self.submissions[submission.filename] = submission

    def student_csv(self, student, desired_section=None):
        filepaths = {}
        grades_report = self.student_report(student)

        fieldnames = ["Assignment"] + self.classroom.grading_categories
        for sectionname, grades in grades_report.items():
            if desired_section and desired_section.filename != sectionname:
                continue
            if not os.path.exists(f"{self.csv_folderpath}/{sectionname}"):
                os.mkdir(f"{self.csv_folderpath}/{sectionname}")
            filepath = f"{self.csv_folderpath}/{sectionname}/{student.filename}.csv"
            with open(filepath, "w", newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                # Write each dictionary as a row in the CSV file
                for courseworkname, report in grades.items():
                    row = {'Assignment': f"{report['title']} - [rubric]({report['rubric_url']}) - [GC]({report['submission_url']})"}
                    for category in self.classroom.grading_categories:
                        row[category] = report.get(category, {}).get('grade', '')
                    writer.writerow(row)
                filepaths[sectionname] = filepath
        return filepaths

    def section_csv(self, section):
        roster = section.students
        fieldnames = ["Student Num", "Student Name"] + self.cw_headings
        filepath = f"{self.csv_folderpath}/{section}.csv"
        grades = self.section_report(section, 'Student Name')
        with open(filepath, "w", newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            # Write each dictionary as a row in the CSV file
            for student_name, report in grades.items():
                row = {}
                for coursework, scores in report.items():
                    if type(scores) is not dict:
                        continue
                    row[scores['heading']] = scores['overall']

                row['Student Num'] = report['Student Num']
                row['Student Name'] = student_name
                writer.writerow(row)
        return filepath

