class GradesRepo:
    link_targets = {}
    path = "/Users/pil/Documents/GitHub/grades"
    if not os.path.exists(path + "/students"):
        os.mkdir(path + "/students")
    url = "https://american-community-school-of-amman.github.io/grades"
    domain = url.split("//")[1].split("/")[0]
    
    @classmethod
    def add_file(cls, submission):
        if not UPDATE_GRADES_REPO:
            return GradesRepo.get_url(submission)
        logger.info(f"CREATING grade report for {submission}")
        student_path = cls.path + submission.student.relative_path
        if not os.path.exists(student_path):
            os.mkdir(student_path)
        with open(f"{student_path}/{submission.filename}.md", "w") as file:
            file.write(frontmatter.dumps(submission.frontmatter))
        cls.link_targets[submission.filename] = submission.coursework.title
        grade_url = "{}/{}/{}.html".format(cls.url, submission.student.relative_path, submission.filename)    
        return grade_url
    
    @classmethod
    def get_url(cls, submission):
        student_path = os.path.join(cls.path, submission.student.filename)
        if not os.path.exists(student_path):
            return False
        if not os.path.exists(f"{student_path}/{submission.filename}.md"):
            return False
        return "{}/{}/{}.html".format(cls.url, submission.student.filename, submission.filename)
    
    # @classmethod
    # def get_student_report_url(cls, student):
    #     student_path = os.path.join(cls.path, student.filename)
    #     if not os.path.exists(student_path):
    #         return False
    #     if not os.path.exists(f"{student_path}/{.filename}.md"):
    #         return False
    #     return "{}/{}/{}.html".format(cls.url, submission.student.filename, submission.filename)

    @classmethod
    def create_file(cls, submission, content):
        if not UPDATE_GRADES_REPO:
            return GradesRepo.get_url(submission)
        student_path = os.path.join(cls.path, submission.student.filename)
        if not os.path.exists(student_path):
            os.mkdir(student_path)
        with open(f"{student_path}/{submission.filename}.md", "w") as file:
            file.write(f"---\ntitle: {submission.coursework.title.replace(':', '-')}-{submission.student.lastfirst}  \nemail: {submission.student.email}  \n---\n")
            file.write(content)
            logger.info(f"{student_path}/{submission.filename}.md")
        cls.link_targets[submission.filename] = submission.coursework.title
        grade_url = "{}/{}/{}.html".format(cls.url, submission.student.filename, submission.filename)    
        return grade_url
    
    @classmethod
    def delete_file(cls, submission):
        if not UPDATE_GRADES_REPO:
            return GradesRepo.get_url(submission)
        student_path = os.path.join(cls.path, submission.student.filename)
        if os.path.exists(f"{student_path}/{submission.filename}.md"):
            os.remove(f"{student_path}/{submission.filename}.md")   

    @classmethod
    def update_student_index(cls, student):
        student_path = os.path.join(cls.path, student.filename) + "/index.md"
        if not os.path.exists(student_path):
            return False
        with open(student_path, "w") as indexfile:
            indexfile.write(f"---  \nemail: {student.email}  \n---  \n")
            # indexfile.write(f"""<script>var allowedEmail = "{student.email}"; </script> \n<script src="/auth.js"></script>  \n\n""")
            indexfile.write(f"# {student.lastfirst}  \n")
            report = student.grades_report()
            indexfile.write(report)
        return True


    @classmethod
    def update_grade_index(cls):
        if not UPDATE_GRADES_REPO:
            return
        logger.info("UPDATING grades repo index")
        folders =  [f for f in os.listdir(cls.path) if os.path.isdir(os.path.join(cls.path, f)) and f != ".git"]
        folderlinks = ""
        for f in folders:
            folderpath = f"{cls.path}/{f}"
            folderlinks += "* [{}]({})\n".format(f, f+"/")
            # Get all files in the folder
            files = [f[:-3] for f in os.listdir(folderpath) if os.path.isfile(os.path.join(folderpath, f))]

            # Create the Markdown file
            with open(f"{folderpath}/index.md", "w") as indexfile:
                for filename in files:
                    try:
                        indexfile.write("* [{}]({})\n".format(cls.link_targets[filename], os.path.join(f, f"{filename}.html")))
                    except KeyError:
                        pass
                        # logger.info(f"{filename} not in link targets")
        with open(f"{cls.path}/list.md", "w") as file:
            file.write(folderlinks)
        for name, classroom in Classroom.register.items():
             for studentname, student in classroom.students.items():
                 GradesRepo.update_student_index(student)
        cls.git_commit("updating index")
        cls.git_push()

    @classmethod
    def git_commit(cls, message):
        if not UPDATE_GRADES_REPO:
            return 
        logger.info("COMMITTING grades repo")
        repo = Repo(cls.path + "/.git")
        repo.git.add(all=True)
        repo.index.commit(message)


    @classmethod
    def git_push(cls):
        if not UPDATE_GRADES_REPO:
            return 
        logger.info("PUSHING grades repo")
        repo = Repo(cls.path + "/.git")
        origin = repo.remote(name='origin')
        origin.push()