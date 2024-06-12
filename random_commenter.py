import random
comments = {
    "F": [" Has difficulty staying on task and avoiding being distracted and distracting others. Should plan more effectively and complete work earlier on extended tasks to allow more time for revision. Has shown improvement in their ability to engage in learning activities.", " Is fully cognizant of methods and processes used in class to be more successful. Must work to more consistently meet deadlines. Is"],
    "D": [" Has shown improvement in their ability to engage in learning activities. Must push themselves to think deeply about course content and ask good questions. Clearly has a desire to be successful.", " Is fully cognizant of methods and processes used in class to be more successful. Should plan more effectively and complete work earlier on extended tasks to allow more time for revision. Is consistently engaged in learning activities.", " Does a great job of asking questions and seeking learning on topics covered in class. Should use class time more effectively to practice, collaborate, and ask questions. Has shown improvement in their ability to consistently produce work and meet deadlines.", " Shows a particular interest and ability in the subject matter. Needs to be more focused on analysis to improve work and thought processes. Demonstrates genuine curiosity.", " Demonstrates genuine curiosity. Should use class time more effectively to practice, collaborate, and ask questions. Is consistently engaged in learning activities.", " Is consistently engaged in learning activities. Should plan more effectively and complete work earlier on extended tasks to allow more time for revision. Shows a particular interest and ability in the subject matter.", " Utilizes multiple perspectives when analyzing and presenting class material. Should practice self-assessment by identifying strengths and areas for improvement. Takes an active role in discussions.", " Is capable of working independently and seeking out their own resources to solve problems. Must work on mastering the art of cooperation with peers / with the teacher. Demonstrates a conscientious approach to learning.", " Continuously uses feedback to grow and improve. Must work to more consistently meet deadlines. Shows a particular interest and ability in the subject matter.", " Shows a particular interest and ability in the subject matter. Must push themselves to think deeply about course content and ask good questions. Demonstrates significant imagination in their approach to concepts and learning activities.", " Consistently refines and revises actions to improve them. Should use class time more effectively to practice, collaborate, and ask questions. Has shown improvement in their ability to engage in learning activities.", " Is fully cognizant of methods and processes used in class to be more successful. Should plan more effectively and complete work earlier on extended tasks to allow more time for revision. Is consistently engaged in learning activities.", " Demonstrates genuine curiosity. Should consider pursuing this subject further both in school and in personal projects. Shows a particular interest and ability in the subject matter."],
    "C": [" Has shown improvement in their ability to engage in learning activities. Should use class time more effectively to practice, collaborate, and ask questions. Clearly has a desire to be successful.", " Is fully cognizant of methods and processes used in class to be more successful. Should plan more effectively and complete work earlier on extended tasks to allow more time for revision. Is consistently engaged in learning activities.", " Does a great job of asking questions and seeking learning on topics covered in class. Would benefit greatly from asking for help more often. Has shown improvement in their ability to consistently produce work and meet deadlines.", " Shows a particular interest and ability in the subject matter. Needs to be more focused on analysis to improve work and thought processes. Demonstrates genuine curiosity.", " Demonstrates genuine curiosity. Should use class time more effectively to practice, collaborate, and ask questions. Is consistently engaged in learning activities.", " Is consistently engaged in learning activities. Should plan more effectively and complete work earlier on extended tasks to allow more time for revision. Shows a particular interest and ability in the subject matter.", " Utilizes multiple perspectives when analyzing and presenting class material. Should practice self-assessment by identifying strengths and areas for improvement. Takes an active role in discussions.", " Is capable of working independently and seeking out their own resources to solve problems. Would benefit greatly from conferring with the teacher and seeking feedback more often. Demonstrates a conscientious approach to learning.", " Continuously uses feedback to grow and improve. Must work to more consistently meet deadlines. Shows a particular interest and ability in the subject matter.", " Shows a particular interest and ability in the subject matter. Must push themselves to think deeply about course content and ask good questions. Demonstrates significant imagination in their approach to concepts and learning activities.", " Consistently refines and revises actions to improve them. Should use class time more effectively to practice, collaborate, and ask questions. Has shown improvement in their ability to engage in learning activities.", " Is fully cognizant of methods and processes used in class to be more successful. Should plan more effectively and complete work earlier on extended tasks to allow more time for revision. Is consistently engaged in learning activities.", " Demonstrates genuine curiosity. Should consider pursuing this subject further both in school and in personal projects. Shows a particular interest and ability in the subject matter."],
    "B": [" Has shown improvement in their ability to engage in learning activities. Should plan more effectively and complete work earlier on extended tasks to allow more time for revision. Clearly has a desire to be successful.", " Is fully cognizant of methods and processes used in class to be more successful. Would benefit greatly from asking for help more often. Is consistently engaged in learning activities.", " Does a great job of asking questions and seeking learning on topics covered in class. Must work to more consistently meet deadlines. Is fully cognizant of methods and processes used in class to be more successful.", " Shows a particular interest and ability in the subject matter. Must push themselves to think deeply about course content and ask good questions. Demonstrates significant imagination in their approach to concepts and learning activities.", " Demonstrates genuine curiosity. Should practice self-assessment by identifying strengths and areas for improvement. Is consistently engaged in learning activities.", " Consistently refines and revises actions to improve them. Should use class time more effectively to practice, collaborate, and ask questions. Has shown improvement in their ability to engage in learning activities.", " Is consistently engaged in learning activities. Should consider pursuing this subject further both in school and in personal projects. Effectively synthesizes information to generate new ideas and insights.", " Utilizes multiple perspectives when analyzing and presenting class material. Needs to be more focused on analysis to improve work and thought processes. Shows a particular interest and ability in the subject matter.", " Is capable of working independently and seeking out their own resources to solve problems. Should plan more effectively and complete work earlier on extended tasks to allow more time for revision. Is consistently engaged in learning activities.", " Demonstrates a conscientious approach to learning. Would benefit greatly from asking for help more often. Takes an active role in discussions.", " Shows a particular interest and ability in the subject matter. Must work on mastering the art of cooperation with peers / with the teacher. Demonstrates significant imagination in their approach to concepts and learning activities.", " Is fully cognizant of methods and processes used in class to be more successful. Should use class time more effectively to practice, collaborate, and ask questions. Continuously uses feedback to grow and improve.", " Demonstrates genuine curiosity. Should consider pursuing this subject further both in school and in personal projects. Shows a particular interest and ability in the subject matter."],
    "A": [
        " Demonstrates genuine curiosity. Should consider pursuing this subject further both in school and in personal projects. Is consistently engaged in learning activities.", 
        " Does a great job of asking questions and seeking learning on topics covered in class. Should plan more effectively and complete work earlier on extended tasks to allow more time for revision. Has shown significant improvement as a result of their persistence and hard work.", 
        " Shows a particular interest and ability in the subject matter. Purposeful application of thinking processes could enhance problem-solving skills. Routinely presents unique perspectives and ideas.", 
        " Is highly motivated to succeed. Purposeful application of thinking processes could enhance problem-solving skills. Has shown significant improvement as a result of their persistence and hard work.", 
        " Consistently refines and revises actions to improve them. Could push themselves to set higher goals and expectations. Demonstrates a conscientious approach to learning.", " Is capable of working independently and seeking out their own resources to solve problems. Would benefit from checking in with the teacher more often. Shows a particular interest and ability in the subject matter.", " Effectively synthesizes information to generate new ideas and insights. Should look for more opportunities to extend their learning independently. Is consistently engaged in learning activities.", " Utilizes multiple perspectives when processing class material. Would benefit from practicing self-assessment by identifying strengths and areas for improvement more often. Is fully cognizant of methods and processes used in class to be more successful.", "Utilizes multiple perspectives when processing class material. Would benefit greatly from conferring with the teacher and seeking feedback more often. Demonstrates genuine curiosity.", " Analytical practices are demonstrated in a meaningful way. Needs to be more focused on analysis to improve work and thought processes. Shows a particular interest and ability in the subject matter.", " Is sensitive to the thoughts and opinions of others. Should consider pursuing this subject further both in school and in personal projects. Demonstrates significant imagination in their approach to concepts and learning activities.", " Continuously uses feedback to grow and improve. Should plan more effectively and complete work earlier on extended tasks to allow more time for revision. Does a great job of asking questions and seeking learning on topics covered in class.", " Shows a particular interest and ability in the subject matter. Purposeful application of thinking processes could enhance problem-solving skills. Has a strong ability to understand and share feelings of others."]
    }

grade = ""

while True:
    inn = input("Enter a grade (A, B, C, D, F): ")
    if inn != "":
        grade = inn.upper()
    for g in grade:
        if g in comments:
            positives = list(set([comment.split(".")[0].strip() for comment in comments[g]] + [comment.split(".")[2].strip() for comment in comments[g]]))
            negatives = list(set([comment.split(".")[1].strip() for comment in comments[g]]))


            print(g)
            p1 = random.choice(positives)
            n = random.choice(negatives)
            p2 = p1
            while p2 == p1:
                p2 = random.choice(positives)
            # print first sentence in green
            print("\033[92m" + p1 + ".\033[0m", end=" ")
            #print second sentence in red
            print("\033[94m" + n + ".\033[0m", end=" ")
            #print third sentence in blue
            print("\033[92m" + p2 + ".\033[0m")
