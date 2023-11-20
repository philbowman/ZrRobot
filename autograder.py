from git import Repo
from pathlib import Path
from bs4 import BeautifulSoup, Comment
import os, markdown, flatdict, yaml, frontmatter, datetime, csv, shutil
from collections import defaultdict
from dateutil.relativedelta import relativedelta
from models import *
from helpers import *
from logdef import *
from enum import Enum

class GradingCategory(Enum):
    ENGAGEMENT = 8000
    PROCESS = 800
    PRODUCT = 80
    EXPERTISE = 8

    # 0: invalid
    # 1:
    # 2:

    def grade(self, percentage):
        grade = 8 * int(percentage) - 1
        if grade < 1:
            return 0
        return grade

class Rubric(dict):
    style = """        
    <style>
            ul.rubric {
                list-style-type: none;margin-left: 0;padding-left: 1em;text-indent: -1em;
                } 
            .nono:before {
                content: "🔴";
                padding-right: 5px;
                }
            .yesyes:before {
                content: "🟢";
                padding-right: 5px;
                }
            .maybemaybe:before {
                content: "🟡";
                padding-right: 5px;
                }
            .nomatter:before {
                content: "⚪";
                padding-right: 5px;
                }        
        </style>
        """

    def __init__(self, r, submission, problemset):
        super().__init__(r)
        self.problemset = problemset
        self.submission = submission

        self.cur_criterion = None
        self.cur_category = None
        self.cur_problem = None
        
        self['title'] = problemset.get_title()
        self.setdefault('sequence', 0)
        self.setdefault('requirement_type', 'REQUIRED')
        self['item_id'] = problemset.id_string()
        self.setdefault('problems', {})
        self['num_required'] = problemset.num_required
        self.setdefault('parent', None)
        self['grades'] = {}

        self.cur_problemset = self
        self.problemsets = {problemset.id_string(): self}


    def problemset_exists(self, psitem_id):
        if psitem_id in self.problemsets:
            return True
        return False

    def problem(self, psitem=None, psitem_id=None):
        if not psitem and not psitem_id:
            self.cur_problem = None
            return self.criterion()
        
        if not psitem_id:
            psitem_id = psitem.id_string()
        
        # handle added problemsets
        if psitem_id.startswith('ps-'):
            if not self.problemset_exists(psitem_id):
                item_details = {
                    'item_id': psitem_id,
                    'title': psitem.get_title(),
                    'sequence': psitem.sequence,
                    'requirement_type': psitem.requirement_type.name,
                    'comfort_level': psitem.comfort_level.name,
                    'grades': {},
                }
                self.problemsets[psitem_id] = Rubric(item_details, self.submission, psitem.nested_problemset)
                item_details['problems'] = self.problemsets[psitem_id]['problems']
                self.problemsets[psitem_id]['parent'] = self['item_id']
                self['problems'][psitem_id] = item_details
            self.cur_problem = self['problems'][psitem_id]
            return self.problemsets[psitem_id]
        
        # handle added problems
        elif psitem_id not in self['problems']:
            self['problems'][psitem_id] = {
                'item_id': psitem_id,
                'title': psitem.get_title(),
                'sequence': psitem.sequence,
                'requirement_type': psitem.requirement_type.name,
                'comfort_level': psitem.comfort_level.name,
                'grades': {},
                'criteria': {}
            }                       
        
        self.cur_problem = self['problems'][psitem_id]        

        return self

    # the problem set should already exist when this is called. 
    # the topmost parent problemset is self, which is added to self.problemsets on instantiation
    # def ps(self, psitem=None, psitem_id=None):
    #     if not psitem and not psitem_id:
    #         psitem_id = self['psitem_id']            
    #     elif not psitem_id:
    #         psitem_id = psitem.id_string()

    #     self.cur_problemset = self.problemsets[psitem_id]
    #     return self.cur_problemset

    def criterion(self, criterion_title=None, max_points=1):
        if not criterion_title:
            self.cur_criterion = None
            return self.category()
        if criterion_title not in self.cur_problem['criteria']:
            self.cur_problem['criteria'][criterion_title] = {'title': criterion_title, 'grading_categories': [], 'score': -1, 'max_points': max_points, 'grades': {}}
        self.cur_criterion = self.cur_problem['criteria'][criterion_title]
        return self
    
    def category(self, category_title=None):
        if not category_title:
            self.cur_category = None
            return self
        cat = GradingCategory[category_title.upper()]
        if cat.name not in self.cur_criterion['grading_categories']:
            self.cur_criterion['grading_categories'].append(cat.name)
        self.cur_category = cat
        return self
    
    def score(self, input_score=None, max_points=None):
        if input_score is not None and max_points is not None:
            self.cur_criterion['score'] = input_score
            self.cur_criterion['max_points'] = max_points

            # if not self.cur_criteria['grading_categories']:
            #     self.cur_criteria['grades'].append(int(input_score / max_points) * 8 - 1)
            # else:
            #     
            #         

        return self.cur_criterion['score']
    
    def overall(self, input_problem=None):
        if not input_problem:
            problem = self
        else:
            problem = input_problem
        overall = {}
        for category, grades in problem['grades'].items():
            overall[category] = bool_avg(grades, problem.get('num_required'))
        return overall
    
    @staticmethod
    def combine_grades(source, target):
        for key, value in source.items():
            if type(value) is dict:
                target.setdefault(key, {})
                target[key] = combine_dict(value, target[key])
            elif type(value) is list:
                target.setdefault(key, [])
                target[key] += value
            elif type(value) is int:
                target.setdefault(key, [])
                target[key].append(value)
            else:
                target[key] = value
        return target

    @staticmethod
    def best_problem(problems):
        if not problems:
            return {}
        best = list(problems.keys())[0]
        for problem_id, problem in problems.items():
            if bool_avg(problem['avg_grades']) > bool_avg(problems[best]['avg_grades']):
                best = problem_id
        return problems.pop(best)

    def total_scores(self):
        num_required = self['num_required']
        num_completed = 0
        choice_grades = {}

        for problem_id, problem in self['problems'].items():
            if problem['item_id'].startswith('ps-'):
                self.problemsets[problem['item_id']].total_scores()
                problem['grades'] = self.problemsets[problem['item_id']]['grades']
                problem['overall'] = self.problemsets[problem['item_id']]['overall']
            else:
                for criterion_title, criterion in problem['criteria'].items():
                    for category in criterion['grading_categories']:
                        cat = GradingCategory[category]
                        criterion['grades'][category] = [cat.grade(criterion['score'] / criterion['max_points'])]
                        problem.setdefault('grading_categories', [])
                        problem.setdefault('avg_grades', [])
                        problem['grading_categories'].append(category)
                        problem['avg_grades'] += criterion['grades'][category]
                    self.combine_grades(criterion['grades'], problem['grades'])
                problem['overall'] = self.overall(problem)
            if problem['requirement_type'] == 'REQUIRED':
                self.combine_grades(problem['overall'], self['grades'])
                num_completed += 1
            elif problem['requirement_type'] == 'CHOICE':
                choice_grades[problem_id] = problem
        
        while num_completed < num_required:
            best_problem = self.best_problem(choice_grades)
            self.combine_grades(best_problem.get('overall', {}), self['grades'])
            num_completed += 1

        self['overall'] = self.overall()
        return self
    
    # elif not self.cur_criterion:


      
        

    # def __dict__(self):
    #     d = {}
    #     for k, v in self['problems'].items():
    #         if k.startswith('ps-'):
    #             d[k] = dict(self['problems'][k].html())
    #         else:
    #             d[k] = dict(self['problems'][k])
    #     return d

    def html_grades_oneline(self, grades):
        return f"{','.join([str(g) for g in grades.values()])} ({', '.join(list(set(k for k in grades.keys())))})"

    def html_problem(self, problem, requirement_type):
        grades = [g for g in problem["grades"].values()]
        requirement_type = problem["requirement_type"]        
        html_content = f"<li class='{self.html_grade_class(grades, requirement_type)}'> {sum([0 for i in [problem['sequence']] if i is None] + [i for i in [problem['sequence']] if i is not None ])}. {problem['title']}:  ({problem['requirement_type']})"
        html_content += '<ul class="rubric criteria">'
        for criterion, grade in problem['criteria'].items():
            html_content += f"<li class='{self.html_grade_class([v for v in grade['grades'].values()], requirement_type)}'> {grade['title']}: {grade['score']}/{grade['max_points']} = {self.html_grades_oneline(grade['grades'])}"
            # html_content += self.html_grades(grade['grades'], requirement_type)
            html_content += '</li>'
        html_content += '</ul></li>'
        return html_content


    def html_problemset(self, problemset, requirement_type, level):
        grades = [g for g in problemset["grades"].values()]
        requirement_type = problemset["requirement_type"]
        html_content = f"<li class='{self.html_grade_class(grades, requirement_type)}'> {int(problemset['sequence'])}. {problemset['title']}:  ({problemset['requirement_type']})"
        html_content += self.html_grades(problemset['grades'], requirement_type)
        html_content += '<ul class="rubric">'
        for problem_id, problem in problemset['problems'].items():
            if problem_id.startswith("ps-"):
                html_content += self.html_problemset(problem, requirement_type, level+1)
            else:
                html_content += self.html_problem(problem, requirement_type)
        html_content += '</ul><li>'
        return html_content
    
    def html_grades(self, grades, requirement_type):
        html_content = '<ul class="rubric grades">'
        for category, grade in grades.items():
            html_content += f"<li class={self.html_grade_class(grade, requirement_type)}> {category}:  {grade}</li>"
        html_content += '</ul>'
        return html_content

    def html_grade_class(self, grades, requirement_type):
        if type(grades) is not list:
            grade = [grades]
        else:
            grade = grades
        classes = []
        c = "nomatter"
        for g in grade:
            if type(g) is list:
                classes.append(self.html_grade_class(g, requirement_type))
            elif int(g) < 7 and int(g) > 3:
                classes.append("maybemaybe")
            elif int(g) > 6:
                classes.append("yesyes")
            else:
                classes.append("nono")
        if "yesyes" in classes:
            if "nono" in classes or "maybemaybe" in classes:
                c = "maybemaybe"
            else:
                c = "yesyes"
        elif "maybemaybe" in classes:
            c = "maybemaybe"
        elif requirement_type == 'REQUIRED':
            c = "nono"
        return c

    def html(self):

        html_content = self.style
        html_content += "<h1>" + self['title'] + "</h1>"
        html_content += f"<h2 class={self.html_grade_class([v for v in self['overall'].values()], 'REQUIRED')}>Overall</h2>"
        html_content += self.html_grades(self['overall'], self['requirement_type'])
        html_content += self.html_problemset(self, 'REQUIRED', 2)

        

        return html_content

class AutoGrader():
    def __init__(self, problem, categories=None):
        if not categories:
            self.grading_categories = ["Engagement", "Process", "Product", "Expertise"]
        self.problem = problem
        if problem.autograder:
            self.grader = getattr(self, problem.autograder)
        else:
            self.grader = self.no_grader

    def __str__(self):
        return self.grader.__name__

    def grade(self, rubric):
        return self.grader(rubric)

    def no_grader(self, rubric):
        return {}

    def submit50(self, rubric):
        rubric.criterion('style50').category('PRODUCT').score(0, 1)
        rubric.criterion('check50').category('EXPERTISE').score(0, 1)
        
        problemsubmission = rubric.submission.student.get_submission_for_problem(self.problem)

        if problemsubmission:
            rubric.criterion('style50').category('PRODUCT').score(problemsubmission.style50_score, 1)
            rubric.criterion('check50').category('EXPERTISE').score(problemsubmission.checks_passed, problemsubmission.checks_run)

        return rubric


#     def overall_grades(self, owner, rubric_only=False):
#         # rubric = {}
#         # for category in owner.getvalue('coursework', owner).classroom.grading_categories:
#         #     rubric[category] = {category: {"user": {"overall": owner.getvalue(f'overall_{category}',)}}}
#         # rubric = Rubric({"overall": score, "maxPoints": score}, owner, basic={}, allow_manual_changes=False)
#         # if rubric_only:
#         #     return rubric
#         # owner.rubric = rubric
#         # return owner.rubri
#         pass


#     def grade_learning_behaviors(self, submission):
#         submission.rubric['Not Counted']['Learning Behaviors']['auto']['turned in'] = int(submission.turned_in())
#         submission.rubric['Not Counted']['Learning Behaviors']['auto']['submitted on time'] = int(not submission.late)
#         if submission.student_materials():
#             submission.rubric.remove_comment("No work is attached.")
#         elif self.coursework.is_due():
#             submission.rubric.mark_zero(user=True)
#             submission.rubric.comment("No work is attached.")
#         submission.rubric['Not Counted']['Learning Behaviors']['auto']['is in the class'] = 1

#     # def grade(self, submission):
#     #     if submission.rubric.get('Not Counted') and submission.rubric.rows('Not Counted'):
#     #         self.grade_learning_behaviors(submission)
#     #     self.grader(submission)
#     #     if "MISSING" in submission.status and submission.coursework.is_due():
#     #         submission.rubric.blank()
#     #         # if submission.rubric.get('Not Counted'):
#     #             # submission.rubric['Not Counted']['Learning Behaviors']['user']['is a good person'] = 5
            
#     #     if submission.status == "RESUBMITTED" and submission.rubric.is_complete():
#     #         if submission.rubric.get('Not Counted') and submission.rubric.rows('Not Counted'):
#     #             submission.rubric['Not Counted']['Learning Behaviors']['user']['is a good person'] = "_"
#     #         else:
#     #             submission.rubric.blank(auto=False)
        
#     #     overall = submission.rubric.total_scores()
#     #     # if submission.assignedGrade is not None and submission.assignedGrade != overall:
#     #     #     submission.draftGrade = overall
#     #     submission.rubric.updateTimestamp()
#     #     return submission.rubric

    @runtimer
    def multipage_website(self, owner, rubric_only=False):
        """
        - images on every page that are resized using the height or width html attribute. Be sure the URL does not begin with file:// as that will not display correctly on the live website https://htmlreference.io/element/img/

        ### [Links](https://www.w3schools.com/html/html_links.asp)
        - at least 1 external link (i.e., to a webpage that is not yours) on each page
        - index.html and at least 2 other html files with content on them
        - internal links between index.html and your other pages
        - External, Internal, and Inline CSS https://www.w3schools.com/css/css_howto.asp
        - several tags with inline style added
        - external style sheet with CSS rules
        - `<style>` section in the head of at least one of the pages
        ### [CSS selectors] (https://www.w3schools.com/css/css_selectors.asp)
        - select by `id`, `class` , and `tag` somewhere in the `<style>` tags and/or an external style sheet
        - all of these tags: `<img>`, `<a>`, `<p>` ,` <html>` , `<body> `, `<head> `,`<title>`, (`<h1>`,` <h2>`, etc)
        - all of these css attributes: `font-family`, `background-color`, `color`, `font-size`
        - additional tags and CSS attributes chosen by you from the attached resources above or elsewhere. There should be a variety to get full credit.
        """
        if rubric_only:
            rubric = {
                'Expertise': {
                    "Structure": {
                        "auto": {
                            "`index.html` exists": 1, 
                            "External style sheet `.css` file exists": 1, 
                            "At least 3 `.html` files exist": 1, 
                            "None of the URLs on the site point to locations on the dev's computer (i.e., don't begin with `file://`)": 1, 
                            "Each page is accessible via an internal link from another page": 1, 
                            "At least 1 external link on any page": 1,
                            "Link to live site submitted": 1,
                            "Link to repo submitted": 1
                        }},
                    "HTML": {
                        "auto":{
                            "Exactly 1 opening `<html>` tag on each page": 1, 
                            "No content after closing `</html>` tag on each page": 1, 
                            "Exactly 1 `<head>`...`</head>` section on each page": 1, 
                            "Exactly 1 `<title>`...`</title>` on each page": 1, 
                            "Exactly 1 `<body>`...`</body>` on each page": 1, 
                            "At least one heading (`<h1>`...`</h1>`, `<h2>`...`</h2>`, etc.)  on any page": 1, 
                            "At least 1 `<p>`...`</p>` on any page": 1, 
                            "List (`<ul>` or `<ol>` and `<li>`) or table on any page": 1, 
                            "At least one image on each page": 1, 
                            "The height or width attribute is used on any image": 1, 
                            "External style sheet, `<style>`...`</style>` section, or inline style (`style=""`) on each page": 1, 
                        }}, 
                    "CSS":{
                        "auto": {
                            "External style sheet is linked to at least one page": 1, 
                            "CSS Classes are defined and used on any page": 1, 
                            "CSS tag/element selectors are defined and used on any page": 1, 
                            "Inline CSS AND/OR ID selectors are used on any page": 1, 
                            "CSS attribute background or background-color in any style rule": 1, 
                            "CSS attribute border is used in any style rule": 1, 
                            "CSS font attributes are used (font-family, font-size, color, and/or other font properties) in any style rule": 1
                        }
                }}}
            return Rubric(rubric, owner)
        
        projectrepo = ProjectRepo(owner)
        projectrepo.website_init()
        repo = projectrepo.repo
        if not repo:
            return owner.rubric
        rubric = {
            'Expertise': {
                "Structure": {
                    "auto": {
                        "`index.html` exists": int(projectrepo.file_exists('index.html')), 
                        "External style sheet `.css` file exists": int(projectrepo.file_exists('*.html')), 
                        "At least 3 `.html` files exist": min(1, round(projectrepo.count_filetype('.html')/3, 1)), 
                        "None of the URLs on the site point to locations on the dev's computer (i.e., don't begin with `file://`)": int(bool(projectrepo.valid_links or projectrepo.valid_images) and not bool(projectrepo.local_links)), 
                        "Each page is accessible via an internal link from another page": int(bool(projectrepo.valid_links and projectrepo.pages_linked_internally())), 
                        "At least 1 external link on any page": int(bool(projectrepo.stats['external_link'])),
                        "Link to live site submitted": int(projectrepo.submitted_link_to_livesite()),
                        "Link to repo submitted": int(projectrepo.submitted_link_to_repo())
                    }}}   
            }
        if projectrepo.stats['html_count'] > 0:
            rubric['Expertise']['HTML'] = {
                "auto":{
                    "Exactly 1 opening `<html>` tag on each page": round(projectrepo.stats['html_tags'] / projectrepo.stats['html_count'], 1), 
                    "No content after closing `</html>` tag on each page": round(projectrepo.stats['nojunk'] / projectrepo.stats['html_count'], 1), 
                    "Exactly 1 `<head>`...`</head>` section on each page": round(projectrepo.stats['head_tag'] / projectrepo.stats['html_count'], 1), 
                    "Exactly 1 `<title>`...`</title>` on each page": round(projectrepo.stats['title_tag'] / projectrepo.stats['html_count'], 1), 
                    "Exactly 1 `<body>`...`</body>` on each page": round(projectrepo.stats['body_tag'] / projectrepo.stats['html_count'], 1), 
                    "At least one heading (`<h1>`...`</h1>`, `<h2>`...`</h2>`, etc.)  on any page": int(bool(projectrepo.stats['heading_tag'])),
                    "At least 1 `<p>`...`</p>` on any page": int(bool(projectrepo.stats['p_tag'])),
                    "List (`<ul>` or `<ol>` and `<li>`) or table on any page": int(bool(projectrepo.stats['list_tag'])),
                    "At least one image on each page": int(bool(projectrepo.images_per_page)),
                    "The height or width attribute is used on any image": int(bool(projectrepo.images_per_page)), 
                    "External style sheet, `<style>`...`</style>` section, or inline style (`style=""`) on each page": round(projectrepo.stats['css'] / projectrepo.stats['html_count'], 1), 
                }} 
            rubric['Expertise']["CSS"] = {
                "auto": {
                    "External style sheet is linked to at least one page": int(bool(projectrepo.stats['css'])), 
                    "CSS Classes are defined and used on any page": int(bool(projectrepo.stats['css'])), 
                    "CSS tag/element selectors are defined and used on any page": int(bool(projectrepo.stats['css'])), 
                    "Inline CSS AND/OR ID selectors are used on any page": int(bool(projectrepo.stats['inline_css'] or projectrepo.stats['pages_with_ids'])), 
                    "CSS attribute background or background-color in any style rule": int(projectrepo.stats['background_rule']), 
                    "CSS attribute border is used in any style rule": int(projectrepo.stats['border_rule']), 
                    "CSS font attributes are used (font-family, font-size, color, and/or other font properties) in any style rule": int(projectrepo.stats['font_rule']), 
                }

        }
        owner.rubric.unify(rubric)
        owner.rubric['statistics'] = projectrepo.stat_string
        return owner.rubric

    @runtimer
    def website_project(self, owner, rubric_only=False):
        if rubric_only:
            rubric = {
                'Expertise': {
                    "Structure": {
                        "auto": {
                            "`index.html` exists": 1, 
                            "External style sheet `.css` file exists": 1, 
                            "At least 3 `.html` files exist": 1, 
                            "None of the URLs on the site point to locations on the dev's computer (i.e., don't begin with `file://`)": 1, 
                            "Each page is accessible via an internal link from another page": 1, 
                            "At least 1 external link on any page": 1,
                            "Link to live site submitted": 1,
                            "Link to repo submitted": 1
                        }},
                    "HTML": {
                        "auto":{
                            "Exactly 1 opening `<html>` tag on each page": 1, 
                            "No content after closing `</html>` tag on each page": 1, 
                            "Exactly 1 `<head>`...`</head>` section on each page": 1, 
                            "Exactly 1 `<title>`...`</title>` on each page": 1, 
                            "Exactly 1 `<body>`...`</body>` on each page": 1, 
                            "At least one heading (`<h1>`...`</h1>`, `<h2>`...`</h2>`, etc.)  on any page": 1, 
                            "At least 1 `<p>`...`</p>` on any page": 1, 
                            "List (`<ul>` or `<ol>` and `<li>`) or table on any page": 1, 
                            "Comments (`<!-- this is a comment -->`) on any page": 1, 
                            "At least one image on each page": 1, 
                            "The height or width attribute is used on any image": 1, 
                            "External style sheet, `<style>`...`</style>` section, or inline style (`style=""`) on each page": 1, 
                        }}, 
                    "CSS":{
                        "auto": {
                            "External style sheet is linked to at least one page": 1, 
                            "CSS Classes are defined and used on any page": 1, 
                            "CSS tag/element selectors are defined and used on any page": 1, 
                            "Inline CSS AND/OR ID selectors are used on any page": 1, 
                            "CSS attribute background or background-color in any style rule": 1, 
                            "CSS attribute border is used in any style rule": 1, 
                            "CSS font attributes are used (font-family, font-size, color, and/or other font properties) in any style rule": 1, 
                            "Bootstrap styles are linked on any page": 1, 
                            "Bootstrap classes are used on any page": 1, 
                            "At least one styled `<div>`...`</div>` on any page": 1 
                        },
                        "user":{
                            "The design employs the box model in some way": 1
                        }
                }},
                "Product": {
                    "The Website": {
                            "user": {
                                    "has real value for its intended users and/or is particularly ambitious and successful": 1,
                                    "has a clear purpose and audience": 1,
                                    "is designed and curated purposefully": 1,
                                    "does not throw errors in the console": 1
                            },
                            "auto": {
                                    "submitted": 4
                            }
                        },
                    "The Layout": {
                            "user": {
                                "demonstrates significant ambition, revision work and fine tuning": 1,
                                "is appropriate for the content & purpose": 1,
                                "is consistent and/or complimentary throughout the site": 1,
                                "displays as intended without bugs": 1
                            },
                            "auto": {
                                    "submitted": 4
                            }
                    },
                }
            }
            return Rubric(rubric, owner)
        
        projectrepo = ProjectRepo(owner)
        projectrepo.website_init()
        repo = projectrepo.repo
        if not repo:
            return owner.rubric
        rubric = {
            'Expertise': {
                "Structure": {
                    "auto": {
                        "`index.html` exists": int(projectrepo.file_exists('index.html')), 
                        "External style sheet `.css` file exists": int(projectrepo.file_exists('*.html')), 
                        "At least 3 `.html` files exist": min(1, round(projectrepo.count_filetype('.html')/3, 1)), 
                        "None of the URLs on the site point to locations on the dev's computer (i.e., don't begin with `file://`)": int(bool(projectrepo.valid_links or projectrepo.valid_images) and not bool(projectrepo.local_links)), 
                        "Each page is accessible via an internal link from another page": int(bool(projectrepo.valid_links) and bool(projectrepo.pages_linked_internally())), 
                        "At least 1 external link on any page": int(bool(projectrepo.stats['external_link'])),
                        "Link to live site submitted": int(projectrepo.submitted_link_to_livesite()),
                        "Link to repo submitted": int(projectrepo.submitted_link_to_repo())
                    }}},

            "Product": {"The Layout": {"auto": {"submitted": int(bool(owner.student_materials()))*4}}, 
                        "The Website": {"auto": {"submitted": int(bool(owner.student_materials()))*4}}}       
            }
        if projectrepo.stats['html_count'] > 0:
            rubric['Expertise']['HTML'] = {
                "auto":{
                    "Exactly 1 opening `<html>` tag on each page": round(projectrepo.stats['html_tags'] / projectrepo.stats['html_count'], 1), 
                    "No content after closing `</html>` tag on each page": round(projectrepo.stats['nojunk'] / projectrepo.stats['html_count'], 1), 
                    "Exactly 1 `<head>`...`</head>` section on each page": round(projectrepo.stats['head_tag'] / projectrepo.stats['html_count'], 1), 
                    "Exactly 1 `<title>`...`</title>` on each page": round(projectrepo.stats['title_tag'] / projectrepo.stats['html_count'], 1), 
                    "Exactly 1 `<body>`...`</body>` on each page": round(projectrepo.stats['body_tag'] / projectrepo.stats['html_count'], 1), 
                    "At least one heading (`<h1>`...`</h1>`, `<h2>`...`</h2>`, etc.)  on any page": int(bool(projectrepo.stats['heading_tag'])),
                    "At least 1 `<p>`...`</p>` on any page": int(bool(projectrepo.stats['p_tag'])),
                    "List (`<ul>` or `<ol>` and `<li>`) or table on any page": int(bool(projectrepo.stats['list_tag'])),
                    "Comments (`<!-- this is a comment -->`) on any page": int(bool(projectrepo.stats['comment_tag'])),
                    "At least one image on each page": int(bool(projectrepo.images_per_page)),
                    "The height or width attribute is used on any image": int(bool(projectrepo.images_per_page)), 
                    "External style sheet, `<style>`...`</style>` section, or inline style (`style=""`) on each page": round(projectrepo.stats['css'] / projectrepo.stats['html_count'], 1), 
                }} 
            rubric['Expertise']["CSS"] = {
                "auto": {
                    "External style sheet is linked to at least one page": int(bool(projectrepo.stats['css'])), 
                    "CSS Classes are defined and used on any page": int(bool(projectrepo.stats['css'])), 
                    "CSS tag/element selectors are defined and used on any page": int(bool(projectrepo.stats['css'])), 
                    "Inline CSS AND/OR ID selectors are used on any page": int(bool(projectrepo.stats['inline_css'] or projectrepo.stats['pages_with_ids'])), 
                    "CSS attribute background or background-color in any style rule": int(projectrepo.stats['background_rule']), 
                    "CSS attribute border is used in any style rule": int(projectrepo.stats['border_rule']), 
                    "CSS font attributes are used (font-family, font-size, color, and/or other font properties) in any style rule": int(projectrepo.stats['font_rule']), 
                    "Bootstrap styles are linked on any page": int(projectrepo.stats['bootstrap']), 
                    "Bootstrap classes are used on any page": int(projectrepo.stats['bootstrap']), 
                    "At least one styled `<div>`...`</div>` on any page": int(bool(projectrepo.stats['div_tag']))
                },
                "user":{
                    #TODO actually grade this instead of being lazy
                    "The design employs the box model in some way": int(bool(projectrepo.count_filetype('.html')))
                }

        }


        owner.rubric.unify(rubric)
        owner.rubric['statistics'] = projectrepo.stat_string
        return owner.rubric

#     @runtimer
#     def introcs_final(self, owner, rubric_only=False):
#         if rubric_only:
#             rubric = {
#                 'Expertise': {
#                     "Structure": {
#                         "auto": {
#                             "`index.html` exists": 1, 
#                             "External style sheet `.css` file exists": 1, 
#                             "At least 3 `.html` files exist": 1, 
#                             "None of the URLs on the site point to locations on the dev's computer (i.e., don't begin with `file://`)": 1, 
#                             "Each page is accessible via an internal link from another page": 1, 
#                             "At least 1 external link on any page": 1,
#                             "Link to live site submitted": 1,
#                             "Link to repo submitted": 1
#                         }},
#                     "HTML": {
#                         "auto":{
#                             "Exactly 1 opening `<html>` tag on each page": 1, 
#                             "No content after closing `</html>` tag on each page": 1, 
#                             "Exactly 1 `<head>`...`</head>` section on each page": 1, 
#                             "Exactly 1 `<title>`...`</title>` on each page": 1, 
#                             "Exactly 1 `<body>`...`</body>` on each page": 1, 
#                             "At least one heading (`<h1>`...`</h1>`, `<h2>`...`</h2>`, etc.)  on any page": 1, 
#                             "At least 1 `<p>`...`</p>` on any page": 1, 
#                             "List (`<ul>` or `<ol>` and `<li>`) or table on any page": 1, 
#                             "Comments (`<!-- this is a comment -->`) on any page": 1, 
#                             "At least one image on each page": 1, 
#                             "The height or width attribute is used on any image": 1, 
#                             "External style sheet, `<style>`...`</style>` section, or inline style (`style=""`) on each page": 1, 
#                         }}, 
#                     "CSS":{
#                         "auto": {
#                             "External style sheet is linked to at least one page": 1, 
#                             "CSS Classes are defined and used on any page": 1, 
#                             "CSS tag/element selectors are defined and used on any page": 1, 
#                             "Inline CSS AND/OR ID selectors are used on any page": 1, 
#                             "CSS attribute background or background-color in any style rule": 1, 
#                             "CSS attribute border is used in any style rule": 1, 
#                             "CSS font attributes are used (font-family, font-size, color, and/or other font properties) in any style rule": 1, 
#                             "Bootstrap styles are linked on any page": 1, 
#                             "Bootstrap classes are used on any page": 1, 
#                             "At least one styled `<div>`...`</div>` on any page": 1 
#                         }
#                 },
#                     "JS":{
#                         "auto": {
#                             "JS code exists and runs on the live site": 1, 
#                             "JS code is executed from user input": 1, 
#                             "JS code interacts with HTML or CSS on any page/script (e.g., `getElementById()`)": 1, 
#                             "At least 1 variable is initialized (e.g., var foo = 0) and accessed (e.g., Console.log(foo))": 1, 
#                             "At least 1 function is defined and called": 1, 
#                             "Control structures (conditionals (if, else if, else) and/or loops (for, while)) are used on any page/script": 1, 
#                             "Meaningful JS comments exist on any page/script (// this is a comment)": 1
#                         }
#                 }},
#                 "Product": {
#                     "The Website": {
#                             "user": {
#                                     "has real value for its intended users and/or is particularly ambitious and successful": 1,
#                                     "has a clear purpose and audience": 1,
#                                     "is designed and curated purposefully": 1,
#                                     "does not throw errors in the console": 1
#                             },
#                             "auto": {
#                                     "submitted": 4
#                             }
#                         },
#                     "The Layout": {
#                             "user": {
#                                 "demonstrates significant ambition, revision work and fine tuning": 1,
#                                 "is appropriate for the content & purpose": 1,
#                                 "is consistent and/or complimentary throughout the site": 1,
#                                 "displays as intended without bugs": 1
#                             },
#                             "auto": {
#                                     "submitted": 4
#                             }
#                     },
#                 }
#             }
#             return Rubric(rubric, owner)
        
#         projectrepo = ProjectRepo(owner, force_links=True)
#         projectrepo.website_init()
#         repo = projectrepo.repo
#         if not repo:
#             return owner.rubric
#         rubric = {
#             'Expertise': {
#                 "Structure": {
#                     "auto": {
#                         "`index.html` exists": int(projectrepo.file_exists('index.html')), 
#                         "External style sheet `.css` file exists": int(projectrepo.file_exists('*.html')), 
#                         "At least 3 `.html` files exist": min(1, round(projectrepo.count_filetype('.html')/3, 1)), 
#                         "None of the URLs on the site point to locations on the dev's computer (i.e., don't begin with `file://`)": int(bool(projectrepo.valid_links or projectrepo.valid_images) and not bool(projectrepo.local_links)), 
#                         "Each page is accessible via an internal link from another page": int(bool(projectrepo.valid_links) and bool(projectrepo.pages_linked_internally())), 
#                         "At least 1 external link on any page": int(bool(projectrepo.stats['external_link'])),
#                         "Link to live site submitted": int(projectrepo.submitted_link_to_livesite()),
#                         "Link to repo submitted": int(projectrepo.submitted_link_to_repo())
#                     }}},

#             "Product": {"The Layout": {"auto": {"submitted": int(bool(owner.student_materials()))*4}}, 
#                         "The Website": {"auto": {"submitted": int(bool(owner.student_materials()))*4}}}       
#             }
#         if projectrepo.stats['html_count'] > 0:
#             rubric['Expertise']['HTML'] = {
#                 "auto":{
#                     "Exactly 1 opening `<html>` tag on each page": round(projectrepo.stats['html_tags'] / projectrepo.stats['html_count'], 1), 
#                     "No content after closing `</html>` tag on each page": round(projectrepo.stats['nojunk'] / projectrepo.stats['html_count'], 1), 
#                     "Exactly 1 `<head>`...`</head>` section on each page": round(projectrepo.stats['head_tag'] / projectrepo.stats['html_count'], 1), 
#                     "Exactly 1 `<title>`...`</title>` on each page": round(projectrepo.stats['title_tag'] / projectrepo.stats['html_count'], 1), 
#                     "Exactly 1 `<body>`...`</body>` on each page": round(projectrepo.stats['body_tag'] / projectrepo.stats['html_count'], 1), 
#                     "At least one heading (`<h1>`...`</h1>`, `<h2>`...`</h2>`, etc.)  on any page": int(bool(projectrepo.stats['heading_tag'])),
#                     "At least 1 `<p>`...`</p>` on any page": int(bool(projectrepo.stats['p_tag'])),
#                     "List (`<ul>` or `<ol>` and `<li>`) or table on any page": int(bool(projectrepo.stats['list_tag'])),
#                     "Comments (`<!-- this is a comment -->`) on any page": int(bool(projectrepo.stats['comment_tag'])),
#                     "At least one image on each page": int(bool(projectrepo.images_per_page)),
#                     "The height or width attribute is used on any image": int(bool(projectrepo.images_per_page)), 
#                     "External style sheet, `<style>`...`</style>` section, or inline style (`style=""`) on each page": round(projectrepo.stats['css'] / projectrepo.stats['html_count'], 1), 
#                 }} 
#             rubric['Expertise']["CSS"] = {
#                 "auto": {
#                     "External style sheet is linked to at least one page": int(bool(projectrepo.stats['css'])), 
#                     "CSS Classes are defined and used on any page": int(bool(projectrepo.stats['css'])), 
#                     "CSS tag/element selectors are defined and used on any page": int(bool(projectrepo.stats['css'])), 
#                     "Inline CSS AND/OR ID selectors are used on any page": int(bool(projectrepo.stats['inline_css'] or projectrepo.stats['pages_with_ids'])), 
#                     "CSS attribute background or background-color in any style rule": int(projectrepo.stats['background_rule']), 
#                     "CSS attribute border is used in any style rule": int(projectrepo.stats['border_rule']), 
#                     "CSS font attributes are used (font-family, font-size, color, and/or other font properties) in any style rule": int(projectrepo.stats['font_rule']), 
#                     "Bootstrap styles are linked on any page": 1, 
#                     "Bootstrap classes are used on any page": 1, 
#                     "At least one styled `<div>`...`</div>` on any page": int(bool(projectrepo.stats['div_tag']))
#                 }
#                 # "user":{
#                 #     #TODO actually grade this instead of being lazy
#                 #     "The design employs the box model in some way": int(bool(projectrepo.count_filetype('.html')))
#                 # }

#         }
#         if projectrepo.contains_javascript():
#             # for key in owner.rubric['Expertise']['JS']['auto'].keys():
#                     # owner.rubric['Expertise']['JS']['auto'][key] = 1
#             rubric['Expertise']['JS'] = {
#                 "auto": {
#                     "JS code exists and runs on the live site": 1, 
#                     "JS code is executed from user input": 1, 
#                     "JS code interacts with HTML or CSS on any page/script (e.g., `getElementById()`)": int(bool('getElement' in projectrepo.js_all)),
#                     "At least 1 variable is initialized (e.g., var foo = 0) and accessed (e.g., Console.log(foo))": int(any(v in projectrepo.js_all for v in ['var', 'let', 'const'])),
#                     "At least 1 function is defined and called": int(bool('function' in projectrepo.js_all)),
#                     "Control structures (conditionals (if, else if, else) and/or loops (for, while)) are used on any page/script": int(bool(any(v in projectrepo.js_all for v in ['if', 'switch'])  and any(v in projectrepo.js_all for v in ['for', 'while']))), 
#                     "Meaningful JS comments exist on any page/script (// this is a comment)": int(bool('//' in projectrepo.js_all))
#                 }
#         }


#         owner.rubric.unify(rubric)
#         owner.rubric['statistics'] = projectrepo.stat_string
#         return owner.rubric
    
#     def completion_only(self, owner, rubric_only=False):
#         score = 1
#         if type(owner) is Submission:
#             score = int(bool(owner.student_materials()))
#         rubric = Rubric({"overall": score, "maxPoints": score}, owner, basic={}, allow_manual_changes=False)
#         if rubric_only:
#             return rubric
#         owner.rubric = rubric
#         return owner.rubric
    
#     def graded_on_classroom(self, owner, rubric_only=False):
#         owner.scored_on_classroom = True
#         owner.force_regrade = True
#         if type(owner) is Submission:
#             score = int0(owner.get_score(mark_draft=False, from_cr=True))
#             max_score = owner.coursework.cr.get('maxPoints')
#         else:
#             owner.maxPoints = owner.cr.get('maxPoints')
#             score = owner.maxPoints
#             max_score = score
            
#         rubric = {"overall": score, "maxPoints": max_score}

#         if len(owner.categories) == 1:
#             rubric[owner.categories[0]] = {}
#             rubric[owner.categories[0]]['score'] = round(score / max_score * 8)
#         else:
#             i = 0
#             scorestr = str(score + 10000)[-1 * len(str(max_score)):]
#             for category in owner.categories:
#                 rubric[category] = {}
#                 cat_score = int(scorestr[i])
#                 if type(owner) is Submission and owner.coursework.title == "Overall" and cat_score == 0:
#                     cat_score = 1
#                 rubric[category]['score'] = cat_score
#                 i += 1


#             # category_scores = str(crpoints)
#             # i = 0
#             # for category in owner.getvalue('coursework', owner).classroom.grading_categories:
#             #     try:
#             #         point = int(category_scores[i])
#             #         if isinstance(owner, Submission):
#             #             point = "_"
#             #         rubric[category] = {"Score on Classroom": {"user": {"score": point}}}
#             #         i += 1
#             #     except IndexError:
#             #         break
#         owner.rubric = Rubric(rubric, owner, basic={}, allow_manual_changes=False)
#         return owner.rubric
        
#         # score = int0(owner.get_score(mark_draft=False, from_cr=True))
#         # # category_scores = str(score)
#         # # included_categories = [k for k in owner.rubric if k in owner.getvalue('coursework', owner).classroom.grading_categories]
#         # # leading_zeroes = "0" * (len(included_categories) - len(category_scores))
#         # # category_scores = leading_zeroes + category_scores
        
#         # # i = 0
#         # # for category in included_categories:
#         # #     point = category_scores[i]
#         # #     owner.rubric[category]["Score on Classroom"]["user"]["score"] = int(point)
#         # #     i += 1
#         # owner.rubric['overall'] = score
#         # return owner.rubric

#     # def practice_pt(self, owner, rubric_only=False):
#     #     if rubric_only:
#     #         rubric = self.graded_on_classroom(owner, rubric_only)
#     #         rubric.unify({"Product": {"Score on Classroom": {"auto": {"has a pulse": 2}}}})
#     #         return rubric
        
        
#     # def no_grader(self, owner, rubric_only=False):
#     #     existing = owner.getvalue('rubric', {})
#     #     if not [k for k in existing.keys() if k not in ["Not Counted", "comments"]]:
#     #         for category in owner.getvalue('coursework', owner).classroom.grading_categories:
#     #             if isinstance(owner, Submission):
#     #                 existing[category] = {category: {"user": {"overall": '_'}}}
#     #             else:
#     #                 existing[category] = {category: {"user": {"overall": 8}}}
        
#     #     rubric = Rubric(existing, owner)
#     #     if rubric_only:
#     #         return rubric
#     #     return owner.rubric
        
#     def do_not_grade(self, owner, rubric_only=False):
#         if type(owner) is Coursework:
#             owner.submission_required = False
#         rubric = Rubric({"overall": 1, 'maxPoints': 1}, owner, basic={}, allow_manual_changes=False)
#         if rubric_only:
#             return rubric
#         owner.rubric = rubric
#         return owner.rubric
    
#     def get_rubric(self, owner, rubric_only=True):
#         if isinstance(owner, Submission):
#             # make a blank version of the coursework rubric
#             rubric = Rubric(owner.coursework.getvalue('rubric', {}), owner, basic={}).blank()
#             # add previously-scored criteria
#             #rubric.unify(owner.getvalue('rubric', {}), add_criteria=False)
#         else:
#             # get the autograder rubric (marked 100%)
#             rubric = self.grader(owner, rubric_only)

#             # add additional criteria from coursework
#             cwrubric = owner.getvalue('rubric', {})
#             rubric.unify(cwrubric)
#             rubric.comment([])

#         return rubric
#     @runtimer
#     def classic_computer_stan(self, owner, rubric_only=False):
#         if not owner or rubric_only:
#             rubric = {
#                 "Product": {
#                     "Repo": {
#                         "auto": {
#                             "link to repo submitted": 1,
#                             "repo is accessible": 1,
#                             "link to live site submitted": 1,
#                             "live site is accessible": 1
                            
#                         },
#                         "user": {
#                             "demonstrates sophistication or creativity": 1,
#                             "includes all content required by the instructions": 1,
#                             "website displays as intended without error": 2
#                         }
#                     }
#                 },
#                 "Expertise": {
#                     "Markdown": {
#                         "auto": {
#                             "includes an image in the repository": 1,
#                             "includes 7 types of formatting": 5
#                         },
#                         "user": {
#                             "demonstrates sophistication or creativity": 1
                            
#                         }
#                     }
#                 }
#             }
#             rubric = Rubric(rubric, owner)
#             if rubric_only:
#                 return rubric
#         projectrepo = ProjectRepo(owner)
#         projectrepo.md_init()
#         repo = projectrepo.repo
#         if not repo:
#             owner.rubric.mark_zero()
#             return owner.rubric
#         if projectrepo.is_profile_repo():
#             owner.rubric.mark_zero()
#             owner.rubric.comment([])
#             owner.rubric.comment("Wrong link(s) submitted; double check the submission instructions and resubmit.")
#             return owner.rubric
#         rck = owner.rubric['Product']['Repo']['auto']

#         rck["link to repo submitted"] = int(projectrepo.submitted_link_to_repo())
#         rck["repo is accessible"] = int(validate_target(projectrepo.repolink))
#         rck["link to live site submitted"] = int(projectrepo.submitted_link_to_livesite())
#         rck["live site is accessible"] = int(validate_target(projectrepo.livelink))

#         mck = owner.rubric['Expertise']['Markdown']["auto"]
#         mck["includes an image in the repository"] =  int(bool(projectrepo.relative_image_links()))
#         num_md_used = len(projectrepo.md_elements['elements_used'])-2
#         mck["includes 7 types of formatting"] = max(0, min(5, num_md_used))
#         owner.rubric.comment([])
#         owner.rubric['statistics'] = "Elements used: " + ", ".join(projectrepo.md_elements['elements_used'])
#         return owner.rubric

#     def github_account_profile(self, owner, rubric_only=False):
#         if not owner or rubric_only:
#             rubric = {
#                 "Product": {
#                     "Repo": {
#                         "auto": {
#                             "exists and is public": 2,
#                             "is named correctly": 1,
#                             "submitted link leads to profile page": 1,
#                             "link submitted": 3
#                         },
#                         "user": {
#                             "demonstrates sophistication or creativity": 1
#                         }
#                     }
#                 },
#                 "Expertise": {
#                     "Markdown": {
#                         "auto": {
#                             "includes a link": 1,
#                             "includes an image": 1,
#                             "includes 4 other types of formatting": 4
#                         },
#                         "user": {
#                             "demonstrates sophistication or creativity": 1,
#                             "displays original content": 1
#                         }
#                     }
#                 }
#             }
#             rubric = Rubric(rubric, owner)
#             if rubric_only:
#                 return rubric
#         projectrepo = ProjectRepo(owner)
#         projectrepo.md_init()
#         repo = projectrepo.repo
#         if repo:
#             exists = True
#         else:
#             exists = False
#         rck = owner.rubric['Product']['Repo']['auto']
#         rck["exists and is public"] = int(exists)*2
#         rck["is named correctly"] = int(projectrepo.is_profile_repo())
#         rck["submitted link leads to profile page"] = int(projectrepo.submitted_link_to_profile())
#         rck["link submitted"] =int(any(projectrepo.urls))*3 

#         mck = owner.rubric['Expertise']['Markdown']["auto"]
#         mck["includes a link"] = int(len(projectrepo.md_elements['links']) > 0)
#         mck["includes an image"] = int(len(projectrepo.md_elements['images']) > 0)
#         num_md_used = len([e for e in projectrepo.md_elements['elements_used'] if e not in ['images', 'links']])
#         mck["includes 4 other types of formatting"] = min(4, num_md_used)
#         owner.rubric.comment([])
#         owner.rubric['statistics'] = "Elements used: " + ", ".join(projectrepo.md_elements['elements_used'])
#         return owner.rubric



# class Rubric(dict):
#     def __init__(self, input_rubric, owner: Union[Coursework, Submission], basic=None, allow_manual_changes=True):
#         # Initialize this rubric as the basic, base rubric for all assignments. 
        
#         self.allow_manual_changes = allow_manual_changes
#         if basic is None:
#             basic = {"Not Counted": {"Learning Behaviors": {"auto": {"turned in": 1, "submitted on time": 1, "is in the class": 1}, "user": {"is a good person": 5}}}}
#         super().__init__(basic)
#         # set default score and comment
#         self['overall'] = 0
#         self['comments'] = ["Not yet graded"]

#         # set instance variables used by methods
#         if type(owner) is Submission:
#             self.submission = owner
#             self.coursework = owner.coursework
#             self.cw_rubric = owner.coursework.rubric
#         if type(owner) is Coursework:
#             self.submission = None
#             self.coursework = owner
#             self.cw_rubric = self
#         # bring input (either scored criteria or criteria defined in Obsidian) into this rubric
        
#         self.unify(input_rubric)

#     def validate_score(self, score):
#         if int0(score) > int0(self['maxPoints']):
#             return False
#         if "Not Counted" in self.keys():
#             if int0(str(score)[0]) < 5:
#                 return False
#         return True
        
#     def scores(self):
#         report = {}
#         report['overall'] = self['overall']
#         report['maxPoints'] = self['maxPoints']
#         for cat in ["Not Counted"] + self.coursework.classroom.grading_categories:
#             report[cat] = {}
#             report[cat]['score']= self.get(cat, {}).get('overall', "")
#             report[cat]['grade']= self.get(cat, {}).get('grade', "")
#         return report

#     def set_criterion(self, mark, target_criterion, target_categories = [], target_rows = []):
#         categories = ["Not Counted"] + self.coursework.classroom.grading_categories
#         if target_categories:
#             categories = [c for c in categories if c in target_categories]

#         for category in categories:
#             rows = self.rows(category)
#             if target_rows:
#                 rows = [r for r in rows if r in target_rows]
#             for row in rows:
#                 for criterion in self[category][row]['auto']:
#                     if criterion == target_criterion:
#                         self[category][row]['auto'] = mark
#                 for criterion in self[category][row]['user']:
#                     if criterion == target_criterion:
#                         self[category][row]['user'] = mark
#         return self

#     def updateTimestamp(self):
#         tscomment = f"Updated {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}" 
#         if not self.get('comments'):
#             self['comments'] = [tscomment]
#         else:
#             self['comments'][0] = tscomment
    
#     def to_frontmatter(self):   
#         d = {}
#         for category in self.coursework.classroom.grading_categories + ["Not Counted"]:
#             if category not in self.keys():
#                 continue
#             # d.setdefault(f"{category}", {})
#             for r in self.rows(category):
#                 if not self[category][r].get('user'):
#                     continue
#                 # d[category].setdefault(r, {"user": {}})
#                 for c in self[category][r].get('user', {}).keys():
#                     d.setdefault(f"{category}:{r}:user", {})
#                     d[f"{category}:{r}:user"][c] = self[category][r]['user'][c]
#             # if not d[f"{category}:{r}:user"]:
#             #     d.pop(f"{category}:{r}:user")
#         d['comments'] = self['comments']
#         fd = dict(flatdict.FlatDict(d))
#         return d
    
#     def user_criteria(self, category, row):
#         return [k for k in self.get(category, {}).get(row, {}).get('user', {}).keys()]
    
#     def auto_criteria(self, category, row):
#         return [k for k in self.get(category, {}).get(row, {}).get('auto', {}).keys()]

#     def rows(self, category):
#         if category not in self:
#             return []
#         return [k for k in self.get(category, {}).keys() if type(self[category][k]) is dict]

#     def categories(self):
#         sorted = []
#         cat = [k for k in self.keys() if type(self[k]) is dict]
#         for c in ["Not Counted"] + self.coursework.classroom.grading_categories:
#             if c in cat:
#                 sorted.append(c)
#         return sorted
    
#     def to_dict(self):
#         d = {r: self[r] for r in self.keys()}
#         return d
#     #chatGPT
#     def unify(self, source, destination=None, add_criteria=True):
#         if not source:
#             self.total_scores()
#             return self
#         if destination == None:
#             destination = self
#         for key, value in source.items():
#             if not add_criteria and not destination.get(key):
#                 continue
#             if isinstance(value, dict):
#                 # Recursively merge nested dictionaries
#                 node = destination.setdefault(key, {})
#                 self.unify(value, node, add_criteria)
#             else:
#                 # Overwrite existing keys or create new ones
#                 destination[key] = value
#         if isinstance(destination, Rubric): 
#             destination.total_scores()
#             if 'comments' in source.keys() and source['comments']:
#                 if 'comments' not in destination.keys() or not destination['comments']:
#                     destination.setdefault('comments', [])
#                     destination['comments'].append(source['comments'][0])
#                 else:
#                     destination['comments'][0] = source['comments'][0]
#                 for comment in source['comments']:
#                     destination.comment(comment)
#         return destination

#     def yaml(self):
#         return str(yaml.dump(dict(self), default_flow_style=False))    

#     def overall(self):
#         if not self.categories():
#             return self['overall']
#         score = ""
#         for category in ["Not Counted"] + self.coursework.classroom.grading_categories:
#             for row in self.rows(category):
#                 score += str(int0(self[category][row].get('score', '_')))
#         self['overall'] = int(score)
#         return self['overall']
    
#     def unify_content_rubric(self, content_rubric=None):
#         if not self.allow_manual_changes:
#             return self
#         if self.submission and not content_rubric:
#             content_rubric = self.submission.getvalue('content_rubric', "")
#         if not self.categories():
#             return self
#         out = {}
#         content_rubric = content_rubric.replace("`⟨", "`<").replace("⟩`", ">`")
#         lines = content_rubric.split("\n")
#         if "<!--comments-->" in lines:
#             out['comments'] = []
#             try:
#                 comments = lines[lines.index("<!--comments-->")+1:lines.index("<!--/comments-->")]
#                 for comment in comments:
#                     if comment.startswith("- "):
                        
#                         out['comments'].append(comment[2:].strip())
#             except ValueError:
#                 pass
#         for line in lines:
#             if line[0:3] != "- [" or line[4:10] != "] <!--":
#                 continue
#             checked = bool(line[3].lower() == "x")
#             keys = line[line.index("<!--")+len("<!--"):line.index("-->")].split(":")
#             if keys == ["force_regrade"]:
#                 if checked:
#                     self.submission.force_regrade = True
#                 continue
#             if len(keys) != 3:
#                 raise MissingData("keys in content rubric are effed")
#             category = keys[0]
#             row = keys[1]
#             kind = keys[2]
#             criterion = line[line.index("-->")+len("-->"):line.index("---")].strip()
#             out.setdefault(category, {})
#             out[category].setdefault(row, {})
#             out[category][row].setdefault(kind, {})
#             try:
#                 if checked:
#                     out[category][row][kind][criterion] = self.cw_rubric[category][row][kind][criterion]
#                 else:
#                     out[category][row][kind][criterion] = self[category][row][kind][criterion]
#             except KeyError:
#                 logger.info(f"line not in cw rubric: {line}")
#         return self.unify(out, add_criteria=False)

#     def editable_report(self):

#         criteria_column_width = 10
#         score_divider = "-" * criteria_column_width
#         rs = ""
#         for category in self.coursework.classroom.grading_categories + ["Not Counted"]:
#             for row in self.rows(category):
#                 rs += f"## {row} ({category}): {self[category][row].get('grade', '')}  \n"
#                 for criterion in self.auto_criteria(category, row):
#                     comment = "<!--{}-->".format(f"{category}:{row}:auto")
#                     check = " "
#                     if int0(self[category][row]['auto'][criterion])/int(self.cw_rubric[category][row]['auto'][criterion]) == 1:
#                         check = "x" 
#                     rs += f"- [{check}] {comment} {criterion}---*auto-scored* ({self[category][row]['auto'][criterion]}/{self.cw_rubric[category][row]['auto'][criterion]})\n"
#                 for criterion in self.user_criteria(category, row):
#                     comment = f"<!--{category}:{row}:user-->"
#                     check = " "
#                     if int0(self[category][row]['user'][criterion])/int(self.cw_rubric[category][row]['user'][criterion]) == 1:
#                         check = "x" 
#                     rs += f"- [{check}] {comment} {criterion}---({self[category][row]['user'][criterion]}/{self.cw_rubric[category][row]['user'][criterion]})\n"
#                 rs += "\n\n"
#         rs = rs.replace("`<", "`⟨").replace(">`", "⟩`")
#         if not self.categories():
#             rs += f"Score: {self['overall']}"
#         if self.submission:
#             heading = self.submission.coursework.title
#             student = self.submission.student.lastfirst + "  \n" + self.submission.status
#             comments = "- " + "  \n- ".join([c for c in self.get('comments', [])])

#             report = "# {}  \n### {}  \n\n- [ ] <!--force_regrade-->REGRADE\n\n  {}  \n{}  \n{}  \n{}".format(
#                 heading,
#                 student,
#                 f"draftGrade: {self.submission.draftGrade}",
#                 f"assignedGrade: {self.submission.assignedGrade}",
#                 self.overall_string(force=True),
#                 rs
#             )
#             if comments:
#                 report += f"\n\n## Comments\n<!--comments-->\n{comments}\n<!--/comments-->"
#             if self.get('statistics'):
#                 report += f"\n\n## Statistics\n{self['statistics']}"
#             # exclude grades repo
#             student_materials = self.submission.student_materials()
#             if student_materials:
#                 attachments_str = "  \n- ".join([str(m) for m in student_materials])
#                 report += f"\n\n## Work Submitted  \n- {attachments_str}"
#             report += f"\n\n---\n[Open in Google Classroom]({self.submission.cr['alternateLink']})"
#             return report
#         return rs

#     def report(self):
#         criteria_column_width = 10
#         score_divider = "-" * criteria_column_width
#         table_heading = f"|  |  |\n| --- | --- |\n"
#         rs = ""
#         for category in self.coursework.classroom.grading_categories + ["Not Counted"]:
#             for row in self.rows(category):
#                 rs += f"## {row} ({category}): {self[category][row].get('grade', '')}\n"
#                 rs += table_heading
#                 for criterion in self.auto_criteria(category, row):
#                     score = int0(self[category][row]['auto'][criterion])
#                     if score == 0:
#                         score_report = "<span style='color:orange;'>__☐__</span>"
#                     elif score / self.cw_rubric[category][row]['auto'][criterion] == 1:
#                         score_report = "<span style='color:green;'>__☑__</span>"
#                     else:
#                         score_report = f"<span style='color:orange;'>{score}/{self.cw_rubric[category][row]['auto'][criterion]}</span>"
#                     rs += f"| {score_report} | {criterion} (*auto-scored*){' ' * (criteria_column_width - len(criterion))} |\n"
#                 for criterion in self.user_criteria(category, row):
#                     score = int0(self[category][row]['user'][criterion])
#                     if score == 0:
#                         score_report = "<span style='color:orange;'>__☐__</span>"
#                     elif score / self.cw_rubric[category][row]['user'][criterion] == 1:
#                         score_report = "<span style='color:green;'>__☑__</span>"
#                     else:
#                         score_report = f"<span style='color:orange;'>{score}/{self.cw_rubric[category][row]['auto'][criterion]}</span>"
#                     rs += f"| {score_report} | {criterion}{' ' * (criteria_column_width - len(criterion))} |\n"
#                 rs += "\n\n"
#         if not self.categories():
#             rs += f"Score: {self['overall']}"
#         if self.submission:
#             heading = self.submission.coursework.title
#             student = self.submission.student.lastfirst
#             comments = "- " + "  \n- ".join([c for c in self.get('comments', [])])
#             report = "{}  \n\n{}  \n{}".format(
#                 f"__[All grades](./)__",
#                 self.overall_string(),
#                 rs,
#             )
#             if comments:
#                 report += f"\n\n## Comments\n{comments}"
#             if self.get('statistics'):
#                 report += f"\n\n## Statistics\n{self['statistics']}"
#             # exclude grades repo
#             student_materials = self.submission.student_materials()
#             if student_materials:
#                 attachments_str = "  \n- ".join([str(m) for m in student_materials])
#                 report += f"\n\n## Work Submitted  \n- {attachments_str}"
#             report += f"  \n\n---\n[Open in Google Classroom]({self.submission.cr['alternateLink']})"
#             return report
#         return rs
        
#     def remove_comment(self, c):
#         if c not in self.keys():
#             return None
#         if c in self['comments']:
#             self['comments'].remove(c)
#         if c in self['comments']:
#             return self.remove_comment(c)
#         return self['comments']

#     def comment(self, c=None):  
#         if c == []:
#             self['comments'] = c
#         if c:
#             if 'comments' not in self.keys():
#                 self['comments'] = [c]
#             elif c.lower().removesuffix(".") not in [com.removesuffix(".").lower() for com in self['comments']]:
#                 self['comments'].append(c)
#             else:
#                 pass
#         return self.get('comments')

#     def total_scores_coursework(self):
#         scores = ""
#         first = True
#         if not self.categories():
#             self['maxPoints'] = self['overall']
#             return self['overall']
#         for category in ["Not Counted"] + self.coursework.classroom.grading_categories:
#             category_scores = []

#             # skip categories not in rubric
#             if not self.get(category):
#                 continue

#             rows = self.rows(category)
#             # if there are no rows, then the rubric is on classroom or it is a simple category grade
#             if not rows:
#                 score = self[category].get('score', 8)
#                 category_scores.append(score)

#             for row in rows:
#                 # total scores for all criteria in row
#                 score = 0                
#                 for criterion in self.auto_criteria(category, row):
#                     score += int0(self[category][row]['auto'][criterion])
#                 for criterion in self.user_criteria(category, row):
#                     score += int0(self[category][row]['user'][criterion])   
#                 self[category][row]['maxScore'] = score        


#             self[category]['maxScore'] = self[category].get('score', 8)
#             scores += str(self[category]['maxScore'])

#         self['overall'] = int0(scores)
#         self['maxPoints'] = int0(scores)
#         return self['overall']
    
#     def total_scores(self):
#         if not self.submission:
#             return self.total_scores_coursework()
#         scores = ""
#         first = True
#         if not self.categories():
#             return self['overall']
#         for category in ["Not Counted"] + self.coursework.classroom.grading_categories:
#             category_scores = []
#             rows = self.rows(category)
#             if not self.get(category):
#                 continue
#             if not rows:
#                 score = self[category].get('score', 0)
#                 category_scores.append(score)
#             for row in rows:
#                 score = 0                
#                 for criterion in self.auto_criteria(category, row):
#                     score += int0(self[category][row]['auto'][criterion])
#                 for criterion in self.user_criteria(category, row):
#                     score += int0(self[category][row]['user'][criterion])   

#                 self[category][row]['score'] = score
#                 self[category][row]['score_8'] = round(8*(score/self[category][row]['maxScore']))                    
#                 self[category][row]['grade'] = lettergrade([int0(self[category][row]['score']), self[category][row]['maxScore']])
#                     # self[category][row]['grade'] = "Not yet graded"
#                 category_scores.append(self[category][row]['score_8'])
#             self[category]['score'] = bool_avg(category_scores)
#             self[category]['grade'] = lettergrade((self[category]['score'], 8))
#             scores += str(self[category]['score'])

#         self['overall'] = int0(scores)
#         self['maxPoints'] = int0(self.cw_rubric['overall'])
#         return self['overall']

#     def overall_string(self, cat=None, force=False):
#         if cat is None:
#             categories = [c for c in self.categories() if c != "Not Counted"]
#         else:
#             categories = [cat]
#         if not categories:
#             return ""
#         # o_s = f"## {self.coursework.title}  \n"
#         o_s = ""
#         if force or self.is_complete():
#             o_s += "| Grade | Category |  \n| --- | --- |  \n"
#             for category in categories:
#                 o_s += f"| {self[category]['grade']} | __{category}__ |  \n"
#                     # o_s += f"\n__{category}__ (overall): {self[category]['grade']}  "
#         else:
#             o_s += "*Not yet graded*"
#         o_s.removeprefix("\n")
#         return o_s

#     def mark_all(self, mark, user=False, auto=True):
#         if mark == 0:
#             categories = self.coursework.classroom.grading_categories
#         else:
#             categories = ["Not Counted"] + self.coursework.classroom.grading_categories
#         for category in categories:
#             for row in self.rows(category):
#                 if auto:
#                     for criterion in self.auto_criteria(category, row):
#                         self[category][row]['auto'][criterion] = mark
#                 if user:
#                     for criterion in self.user_criteria(category, row):
#                         self[category][row]['user'][criterion] = mark
#         self.total_scores()
#         return self

#     def mark_zero(self, user=False, auto=True):
#         return self.mark_all(0, user, auto)
    
#     def blank(self, user=True, auto=True):
#         return self.mark_all("_", user, auto)
    
#     def is_complete(self):
#         try:
#             if not int0(self['Not Counted']['Learning Behaviors']['user']['is a good person']):
#                 return False
            
#         except KeyError:
#             for category in ["Not Counted"] + self.coursework.classroom.grading_categories:
#                 for row in self.rows(category):
#                     for criterion in self.auto_criteria(category, row):
#                         if type(self[category][row]['auto'][criterion]) is str:
#                             return False
#                     for criterion in self.user_criteria(category, row):
#                         if type(self[category][row]['user'][criterion]) is str:
#                             return False
#         return True
    


# # class Page:
# #     targets_filepath = "targets.json"
# #     targets = {}

# #     @classmethod
# #     @runtimer
# #     def load_targets(cls):
# #         if cls.targets:
# #             return
# #         if os.path.exists(cls.targets_filepath):
# #             with open(cls.targets_filepath) as c:
# #                 cls.targets = json.load(c)

# #     @classmethod
# #     @runtimer
# #     def write_targets(cls):
# #         with open(cls.targets_filepath, 'w', encoding='utf-8') as c:
# #             c.write(json.dumps(cls.targets, indent=4))

# #     @classmethod
# #     @runtimer
# #     def validate_target(cls, target, page=None, proj=None, force=FORCE_VALIDATE_URLS):
# #         logger.info("validating " + target)
# #         target = target.strip()
# #         if page and not proj:
# #             proj = page.proj

# #         r = None
# #         # link to nowhere
# #         if not target or target.startswith("#"):
# #             return r
# #         #relative link to home folder
# #         if target == "/":
# #             r = "relative"
        

            
# #         # local link
# #         elif "file://" in target:
# #             r = "local"
# #         elif proj and proj.file_exists(target):
# #             r = "relative"
# #         # url already been validated
# #         elif not force and cls.targets.get(target) != None:
# #             r = cls.targets[target]
# #         else:
# #             r = request_url(target)                    
# #             if r == 404:
# #                 r = False
# #             elif type(r) is requests.models.Response:
# #                 if r.status_code == 404:
# #                     r = False
# #                 elif target.startswith("http://") or target.startswith("https://"):
# #                     r = "external"
# #                 else:
# #                     r = True
# #             else:
# #                 if input("Check manually. Is it valid? (y/n) ").lower() in ["y", "yes"]:
# #                     if target.startswith("http://") or target.startswith("https://"):
# #                         r = "external"
# #                     else:
# #                         r = True
# #                 else:
# #                     r = False
                    

# #         if target not in cls.targets or cls.targets[target] != r:
# #             cls.targets[target] = r
# #         # if proj:
# #         #     if target not in proj.targets:
# #         #         proj.targets.append(target)

# #         return r

# #     def __init__(self, page, proj):
# #         self.page = page
# #         self.proj = proj
# #         self.soup = self.page['soup']
# #         self.html_tags = 0
# #         self.nojunk = 0
# #         self.head_tag = 0
# #         self.body_tag = 0
# #         self.title_tag = 0
# #         self.heading_tag = 0
# #         self.p_tag = 0
# #         self.list_tag = 0
# #         self.comment_tag = 0
# #         self.inline = 0
# #         self.style_tag = 0
# #         self.external_link = 0
# #         self.div_tag = 0
# #         self.linked_sheets = []
# #         self.external_sheet = 0
# #         self.inline_style_rules = []
# #         self.classes_used = []
# #         self.ids_used = []
# #         self.internal_style_rules = []
# #         self.all_tags = []
# #         self.bootstrap = 0
# #         self.script  = 0
# #         self.targets = []
# #         self.image_targets = []
# #         self.valid_links = []
# #         self.broken_links = []
# #         self.local_links = []
# #         self.external_links = []
# #         self.relative_links = []
# #         self.valid_images = []
# #         self.broken_images = []
# #         self.possibly_broken_targets = []
# #         self.js_all = ""
# #         self.find_tags()
# #         self.find_images()
# #         self.find_links()
# #         self.validate_targets()
# #         self.html_stats()
# #         self.css_stats()
# #         self.js_stats()

# #     @runtimer
# #     def js_stats(self):
# #         scripts = self.soup.find_all('script')
# #         if len(scripts) > 0:
# #             self.script = 1
# #         for script in scripts:
# #             self.js_all += "\n" + "\n".join(script.contents)

# #     @runtimer
# #     def find_tags(self):
# #         logger.info("finding tags")
# #         for tag in self.page['soup'].find_all():
# #             self.all_tags.append(str(tag.name))

# #     @runtimer
# #     def find_images(self):
# #         self.images = self.soup.find_all('img')
# #         self.proj.num_images += len(self.images)
# #         for img in self.images:
# #             target = img.get('src')
# #             if target:
# #                 self.image_targets.append(target)
# #             try:
# #                 h = img.height
# #                 self.proj.heightwidth = True
# #             except KeyError:
# #                 try:
# #                     w = img.width
# #                     self.proj.heightwidth = True
# #                 except KeyError:
# #                     pass
# #     @runtimer        
# #     def find_links(self):

# #         links = self.page['soup'].find_all('a')

# #         for link in links:
# #             target = link.get('href')
# #             if target:
# #                 self.targets.append(target)
            


# #     @runtimer
# #     def validate_targets(self):
# #         self.targets = list(set(self.targets))
# #         self.image_targets = list(set(self.image_targets))
# #         for target in self.targets:
# #             validity = Page.validate_target(target, self)
# #             # 18 At least 1 external link is included
# #             if validity == False and target not in self.broken_links:
# #                 self.broken_links.append(target)
# #             elif validity == True and target not in self.valid_links:
# #                 self.valid_links.append(target)
# #             elif validity == "local" and target not in self.local_links:
# #                 self.local_links.append(target)
# #             elif validity == "relative" and target not in self.relative_links:
# #                 self.relative_links.append(target)
# #             elif validity == "external" and target not in self.external_links:
# #                 self.external_links.append(target)
# #                 self.external_link = 1
# #             else:
# #                 if target not in self.possibly_broken_targets:
# #                     self.possibly_broken_targets.append(target)

# #         for target in self.image_targets:
# #             validity = Page.validate_target(target, self)
# #             if validity in [True, "relative", "external"] and target not in self.valid_images:
# #                 self.valid_images.append(target)
# #             elif validity in [False, "local"] and target not in self.broken_images:
# #                 self.broken_images.append(target)
# #             else:
# #                 if target not in self.possibly_broken_targets:
# #                     self.possibly_broken_targets.append(target)

# #     @runtimer
# #     def html_stats(self):
# #         # 6 Exactly 1 opening <html> tag
# #         if len(self.soup.find_all('html')) == 1:
# #             self.html_tags = 1
# #         if len(self.soup.find_all('script')) > 0:
# #             self.script = 1
# #         # 7 No content after closing </html> tag
# #         f = Path(self.page['filename']).read_text()
# #         if f.replace("\n", "").strip()[-len("</html>"):] == "</html>":
# #                 self.nojunk = 1
# #         # 8 Exactly 1 <head>...</head> section
# #         if len(self.soup.find_all('head')) == 1:
# #             self.head_tag = 1
# #         # 9 Exactly 1 <title>...</title>
# #         if len(self.soup.find_all('title')) == 1:
# #             self.title_tag = 1
# #         # 10 Exactly 1 <body>...</body>
# #         if len(self.soup.find_all('body')) == 1:
# #             self.body_tag = 1
# #         # 11 At least one heading (<h1>...</h1>, <h2>...</h2>, etc.)
# #         headings = ["h1", "h2", "h3", "h4", "h5", "h6"]
# #         for h in headings:
# #             if len(self.soup.find_all(h)) > 0:
# #                 self.heading_tag = 1
# #                 break
# #         # 12 At least 1 <p>...</p>
# #         if len(self.soup.find_all('p')) > 0:
# #             self.p_tag = 1
# #         # 13 List (<ul> or <ol> and <li>) or table
# #         lists = ["ul", "ol", "table"]
# #         for l in lists:
# #             if len(self.soup.find_all(l)) > 0:
# #                 self.list_tag = 1
# #                 break
# #         # 14 Comments (<!-- this is a comment -->)
# #         comments = self.soup.findAll(text=lambda text:isinstance(text, Comment))
# #         if len(comments) > 0:
# #             self.comment_tag = 1
# #         # 30 At least one <div>...</div>
# #         divs = self.soup.find_all('div')
# #         if len(divs) > 0:
# #             for tag in divs:
# #                 if 'style' in tag.attrs or 'class' in tag.attrs or 'id' in tag.attrs:
# #                     self.div_tag = 1
# #                     break

# #     @runtimer
# #     def css_stats(self):
# #         # CSS
# #         # 15 External style sheet, <style>...</style> section, or inline style (style="")
# #         for tag in self.soup():
# #             if 'style' in tag.attrs:
# #                 self.inline = 1
# #                 self.inline_style_rules.append(tag.get('style'))
# #             if 'class' in tag.attrs:
# #                 for c in tag.get('class', []):
# #                     self.classes_used.append(c)
# #             if 'id' in tag.attrs:
# #                 self.ids_used.append(id)
# #         style_sections = self.soup.find_all('style')
# #         if len(style_sections) > 0:
# #             self.style_tag = 1
# #             for s in style_sections:
# #                 self.internal_style_rules.append(s.get_text())
# #         self.linked_sheets = self.soup.find_all('link')
# #         if len(self.linked_sheets) > 0:
# #             for l in self.linked_sheets:
# #                 for c in self.proj.filelist['.css']:
# #                     if c in l.get('href', ""):
# #                         self.external_sheet = 1
# #                 if "bootstrap" in l.get("href", ""):
# #                     self.bootstrap = 1

class ProjectRepo():
    @runtimer
    def __init__(self, submission, force_links=False):
        self.submission = submission
        self.repo_path = os.path.join(f"{STUDENTWORK_DIR}/{submission.coursework.filename}", submission.filename)
        self.urls = [m.url for m in submission.materials_objects]
        self.parse_github_urls(force_links=force_links)
        self.repo = self.update_repo()
        self.filelist = self.list_files()  
        self.js_all = ""


    def md_init(self):
        self.md_elements = self.find_md_elements()
        
    def website_init(self):
        self.expertise_overall = 0
        self.scores = []
        self.pages = []
        self.heightwidth = False
        self.num_images = 0
        self.valid_targets = []
        self.local_targets = []
        self.broken_links = []
        self.possibly_broken_targets = []
        self.relative_links = []
        self.targets = []
        self.image_targets = []
        self.style_rules = []
        self.linked_sheets = []
        self.inline_style_rules = []
        self.classes_used = []
        self.classes_defined = []
        self.ids_used = []
        self.ids_defined = []
        self.internal_style_rules = []
        self.tag_selectors = []
        self.all_tags = []
        self.overall_average = 0
        self.structure_score = 0
        self.js = False
        self.make_soup()
        self.make_pages()
        self.parse_css()
        self.parse_js()
        self.stats = self.site_stats()

    @runtimer
    def make_pages(self):
        Page.load_targets()
        if not self.filelist['htmlsoup']:
            return
        for page in self.filelist['htmlsoup']: 
            logger.info(f"making page object for {page['filename']}")
            p = Page(page, self)
            self.pages.append(p)
            for tag in p.all_tags:
                self.all_tags.append(tag)
        self.images_per_page = self.num_images/len(self.filelist['.html'])
        try:
            self.broken_links_percentage = round(len(self.broken_links)/len(self.valid_targets), 1)
        except ZeroDivisionError:
            self.broken_links_percentage = ""

    @runtimer
    def parse_css(self):
        # external style sheets
        for s in self.filelist['.css']:
            sheet = Path(s).read_text().split("}")
            for rule in sheet:
                if "/*" in rule and "*/" in rule:
                    rule = rule.replace(rule[rule.index("/"):rule.index("*/")+2], "")
                if rule:
                    self.style_rules.append(rule.replace("\n", "").strip() + "}")

        for page in self.pages:
            # internal style
            for s in page.internal_style_rules:
                sheet = s.split("}")
                for rule in sheet:
                    if "/*" in rule and "*/" in rule:
                        rule = rule.replace(rule[rule.index("/"):rule.index("*/")+2], "")
                    if rule:
                        self.style_rules.append(rule.replace("\n", "").strip() + "}")
            # inline style
            for r in page.inline_style_rules:
                for rule in r.split(";"):
                    if rule:
                        self.inline_style_rules.append(rule + ";")
            # classes & ids
            for c in page.classes_used:
                self.classes_used.append(c)
            for i in page.ids_used:
                self.ids_used.append(i)
        for rule in self.style_rules:
            if "@" in rule:
                rule = rule[rule.index("{")+1:]
            if "." in rule:
                r = rule[rule.index(".")+1:]
                if "{" in r:
                    self.classes_defined.append(r[:r.index("{")].strip())
            elif "#" in rule:
                r = rule[rule.index("#")+1:]
                if "{" in r:
                    self.ids_defined.append(r[:r.index("{")].strip())
            else:
                if "{" in rule:
                    self.tag_selectors.append(rule[:rule.index("{")])
        for r in self.inline_style_rules:
            new_r = r.replace('\n', "")
            r = new_r.strip()
        self.classes_used = set(self.classes_used)


    @runtimer
    def make_soup(self):
        self.filelist['htmlsoup'] = []
        #print(self.filelist)
        for file in self.filelist['.html']:
            with open(file) as f:
                self.filelist['htmlsoup'].append({'filename': file, 'soup': BeautifulSoup(f, features="html.parser")})

    #chatGPT
    def find_md_elements(self, filelist=None):
        if not filelist:
            filelist = self.filelist['.md']
        element_contents = {
            'headers': [],
            'links': [],
            'images': [],
            'code_blocks': [],
            'strikethrough': [],
            'emphasis': [],
            'strong_emphasis': [],
            'horizontal_rules': [],
            'lists': [],
            'footnotes': [],
            'youtube_videos': [],
            'blockquotes': [],
            'emoji': []
        }

        for file in filelist:
            with open(file, 'r') as f:
                content = f.read()
                element_contents['headers'].extend(re.findall(r'^#+\s(.*)', content, flags=re.MULTILINE))
                element_contents['links'].extend(re.findall(r'\[((?!\!).)*\]\((.*)\)', content))
                element_contents['images'].extend(re.findall(r'!\[.*\]\((.*)\)', content))
                element_contents['code_blocks'].extend(re.findall(r'```.*\n([\s\S]*?)\n```', content))
                element_contents['emphasis'].extend(re.findall(r'\*(.*)\*', content))
                element_contents['strikethrough'].extend(re.findall(r'~~(.*)~~', content))
                element_contents['emoji'].extend(re.findall(r':[a-z0-9_]+:', content))
                element_contents['strong_emphasis'].extend(re.findall(r'\*\*(.*)\*\*', content))
                element_contents['emphasis'].extend(re.findall(r'_(.*)_', content))
                element_contents['strong_emphasis'].extend(re.findall(r'__(.*)__', content))
                element_contents['horizontal_rules'].extend(re.findall(r'---\n', content))
                element_contents['lists'].extend(re.findall(r'^[\*\-\+]\s(.*)', content, flags=re.MULTILINE))
                element_contents['footnotes'].extend(re.findall(r"\[\^([^\]]+)\]:\s+([^\n]+)", content, flags=re.MULTILINE))
                element_contents['youtube_videos'].extend(re.findall(r'(?:<a[^>]*?href=[\'"]|!?\[.*?\]\()https?://(?:www\.)?youtu(?:be\.com/watch\?v=|\.be/)([\w\-]+)(?:&\S+)?(?:[\'"][^>]*?>.*?</a>|\))', content, flags=re.MULTILINE))
                element_contents['blockquotes'].extend(re.findall(r'^> \S.*', content, flags=re.MULTILINE))
                
                html = markdown.markdown(content)
                table_pattern = re.compile(r"<table>.*</table>", re.DOTALL)
                if table_pattern.search(html):
                    element_contents['tables'] = [True]
        element_contents['elements_used'] = [k for k in element_contents if len(element_contents[k])]

        return element_contents

    def contains_javascript(self):
        return self.js

    def parse_js(self):
        for page in self.pages:
            if page.js_all:
                self.js_all += "\n" + page.js_all
        for file in self.filelist['.js']:
            with open(file, "r") as jsfile:
                self.js_all += jsfile.read()
        # if bool([p for p in self.pages if p.script > 0]) or len(self.filelist['js']) > 0:
        while self.js_all[:1] == "\n" or self.js_all[-1:] == "\n":
            self.js_all = self.js_all.removeprefix("\n")
            self.js_all = self.js_all.removesuffix("\n")
        if self.js_all:
            self.js = True


    @runtimer
    def site_stats(self):
        stats = {}
        stats['html_tags'] = 0
        stats['nojunk'] = 0
        stats['head_tag'] = 0
        stats['body_tag'] = 0
        stats['title_tag'] = 0
        stats['heading_tag'] = 0
        stats['p_tag'] = 0
        stats['list_tag'] = 0
        stats['comment_tag'] = 0
        stats['inline'] = 0
        stats['style_tag'] = 0
        stats['external_sheet'] = 0
        stats['external_link'] = 0
        stats['css'] = 0
        stats['div_tag'] = 0
        stats['inline_css'] = 0
        stats['linked_sheets'] = 0
        stats['pages_with_ids'] = 0
        stats['background_rule'] = False
        stats['border_rule'] = False
        stats['font_rule'] = False        
        stats['bootstrap'] = False
        stats['html_count'] = len(self.filelist['.html'])
        self.valid_links = []
        self.broken_links = []
        self.local_links = []
        self.external_links = []
        self.relative_links = []
        self.valid_images = []
        self.broken_images = []
        
        if self.count_filetype('.html') > 0:
            for page in self.pages:
                stats['html_tags'] += page.html_tags
                stats['nojunk'] += page.nojunk
                stats['head_tag'] += page.head_tag
                stats['body_tag'] += page.body_tag
                stats['title_tag'] += page.title_tag
                stats['heading_tag'] += page.heading_tag
                stats['p_tag'] += page.p_tag
                stats['list_tag'] += page.list_tag
                stats['comment_tag'] += page.comment_tag
                stats['external_link'] += page.external_link
                stats['div_tag'] += page.div_tag
                stats['external_sheet'] += page.external_sheet
                stats['inline_css'] += page.inline
                stats['style_tag'] += page.style_tag
                stats['linked_sheets'] += bool(page.linked_sheets)
                
                self.valid_links += page.valid_links + page.external_links + page.relative_links
                self.broken_links += page.broken_links
                self.local_links += page.local_links
                self.external_links += page.external_links
                self.relative_links += page.relative_links
                self.valid_images += page.valid_images
                self.broken_images += page.broken_images
                stats['pages_with_ids'] += int(bool(page.ids_used))
                if page.bootstrap:
                    stats['bootstrap'] = True
                if page.inline or page.style_tag or page.linked_sheets:
                    stats['css'] += 1
                else:
                    stats['css'] += 0
            for s in self.style_rules:
                if "background" in s:
                    stats['background_rule'] = True
                # 26 CSS attribute border is used
                if "border" in s:
                    stats['border_rule'] = True
                # 27 CSS font attributes are used (font-family, font-size, color, and/or other font properties)
                if "font" in s:
                    stats['font_rule'] = True

        self.valid_links = list(set(self.valid_links))
        self.broken_links = list(set(self.broken_links))
        self.local_links = list(set(self.local_links))
        self.external_links = list(set(self.external_links))
        self.relative_links = list(set(self.relative_links))
        self.valid_images = list(set(self.valid_images))
        self.broken_images = list(set(self.broken_images))
        
        stat = []
        stat.append(f"Repository: [{self.reponame}]({self.repolink})")
        stat.append(f"Live site: [{self.livelink}]({self.livelink})")
        stat.append(f"- {len(self.filelist['.css'])} CSS files: {self.filelist['.css_relative']}")
        stat.append(f"- style rules: {self.style_rules}")
        stat.append(f"- inline style: {self.inline_style_rules}")
        stat.append(f"- classes used: {self.classes_used}")
        stat.append(f"- classes defined: {self.classes_defined}")
        stat.append(f"- ids: {[i for i in list(set(self.ids_used)) if i]}")
        stat.append(f"- {self.num_images} valid images: {self.valid_images}")
        stat.append(f"- Broken images: {self.broken_images}")
        stat.append(f"- {len(self.filelist['.html'])} HTML files: {self.filelist['.html_relative']}")
        stat.append(f"- HTMl tags used: {list(set(self.all_tags))}")
        for a, b in {"Valid links": self.valid_links, "Relative targets": self.relative_links, "Local targets": self.local_links, "Broken links": self.broken_links, "Other targets (may or may not be broken)": self.possibly_broken_targets}.items():
            stat.append(f"- {a}: {b}")
        self.stat_string = "  \n" + "  \n".join(stat)
        return stats

    def pages_linked_internally(self):
        num_html = self.count_filetype('.html')
        if not num_html:
            return 0
        
        int_links = 0
        for filename in self.filelist['.html_relative']:
            # print(f"pages: {self.filelist['.html']}")
            # print(f"links: {self.relative_links}")
            for target in self.relative_links:
                if filename.endswith(target.strip()):
                    int_links += 1
                    break

        if int_links == num_html:
            return 1
        else:
            return round(int_links / num_html, 1)

    def count_filetype(self, extension):
        return len(self.filelist.get(extension, []))
    

    def file_exists(self, filename):
        if "*" in filename:
            target = filename.removeprefix("*").removesuffix("*")
            for f in self.filelist['all']:
                if target in f:
                    return True
        elif filename in self.filelist['all']:
            return True
        else:
            for f in self.filelist['allpaths']:
                if f.endswith(filename):
                    return True
        return False
    
    #chatGPT
    def list_files(self):
        filepaths = defaultdict(list)
        filepaths['all'] = []
        for root, dirs, files in os.walk(self.repo_path):
            if '.git' in dirs:
                dirs.remove('.git')
            if '.vscode' in dirs:
                dirs.remove('.vscode')
            for file in files:
                if not file.startswith('.'):
                    filepath = os.path.join(root, file)
                    extension = os.path.splitext(file)[1]
                    filepaths[extension].append(filepath)
                    filepaths['allpaths'].append(filepath)
                    filepaths['all'].append(filepath[filepath.index(self.repo_path)+len(self.repo_path)+1:])
                    filepaths[extension+"_relative"].append(filepath[filepath.index(self.repo_path)+len(self.repo_path)+1:])

        return filepaths

    def relative_image_links(self):
        relative_links = []
        if not self.md_elements['images']:
            return relative_links
        for image in self.md_elements['images']:
            if image in self.filelist['all']:
                relative_links.append(image)
        return relative_links

    def submitted_link_to_repo(self):
        if self.repo_exists:
            return any([u for u in self.urls if u.lower().removesuffix("/").endswith(self.repolink.lower().removeprefix('https://'))])
        return False
    def submitted_link_to_livesite(self):
        if self.livesite_exists:
            return any([u for u in self.urls if u.lower().removesuffix("/").endswith(self.livelink.lower().removeprefix('https://'))])
        return False
    def submitted_link_to_profile(self):
        for u in self.urls:
            if u.removesuffix("/").lower().endswith(f"github.com/{str(self.username).lower()}"):
                return True
        return False

    def is_profile_repo(self):
        return f"{self.username}/{self.username}" in self.repolink

    def exists(self):
        return bool(Page.validate_target(self.repolink))

    def update_repo(self):
        if not self.exists():
            return None
        if os.path.exists(self.repo_path):
            repo = Repo(self.repo_path + "/.git")
            origin = repo.remote(name='origin')
            try:
                origin.pull()
            except Exception as e:
                logger.info(e)
                pass

        else:
            try:
                repo = Repo.clone_from(self.repolink + ".git", self.repo_path)
            except:
                return None
        return repo

    def parse_github_urls(self, urls_in=None, force_links=False):
        if not urls_in:
            urls_in = self.urls
        urls = []
        for url in urls_in:
            if 'american-community-school-of-amman.github.io' in url:
                continue
            url = url.replace("www.github.com", "github.com")
            url = url.strip()
            url = url.removesuffix("/")
            url = url.removesuffix(".git")
            url = url.removeprefix("http://")
            url = url.removeprefix("https://")
            urls.append(url)
        site_urls = []
        repo_urls = []
        usernames = []
        reponames = []
        username = None
        reponame = None

        for url in urls:
            if "github.com" in url:
                if "?" in url:
                    repo_urls.append(url[:url.index("?")])
                else:
                    repo_urls.append(url)
            if url[url.index("."):].startswith(".github.io"):
                site_urls.append(url)

        for url in repo_urls:
            split_url = url.split("/")
            u = split_url[split_url.index('github.com')+1]

            if u not in usernames:
                usernames.append(u)
            try:
                r = split_url[split_url.index(u)+1]
                if r not in reponames:
                    reponames.append(r)
            except IndexError:
                pass
        for url in site_urls:
            split_url = url.split("/")
            u = split_url[0].split(".")[0]
            if u not in usernames:
                usernames.append(u)
            try:
                r = split_url[1]
                if r not in reponames:
                    reponames.append(r)
            except IndexError:
                pass
        usernames = list(set(usernames))
        reponames = list(set(reponames))

        if usernames:
            username = usernames[0]
        if reponames:
            reponame = reponames[0]
        
        profilelink = f"https://github.com/{username}"
        if not reponame and f"github.com/{username}" in urls or f"github.com/{username}/{username}" in urls:
            repolink = f"https://github.com/{username}/{username}"
            livelink = f"https://github.com/{username}"
        else:
            repolink = f"https://github.com/{username}/{reponame}"
            livelink = f"https://{str(username).lower()}.github.io/{reponame}"


        self.username = username
        self.reponame = reponame
        self.repolink = repolink
        self.livelink = livelink
        self.profilelink = profilelink
        self.repo_exists = bool(Page.validate_target(self.repolink))
        self.livesite_exists = bool(Page.validate_target(self.livelink))

        if force_links:
            if self.livelink:
                self.submission.add_attachment(livelink)
            if self.repolink:
                self.submission.add_attachment(repolink)


        github_data = {
            "username": username, 
            "reponame": reponame, 
            "repolink": repolink, 
            "livelink": livelink, 
            "profilelink": profilelink, 
            }

        return github_data