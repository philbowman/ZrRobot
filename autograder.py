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
import markdownify
import html

class GradingCategory(Enum):
    ENGAGEMENT = 1000
    PROCESS = 100
    PRODUCT = 10
    EXPERTISE = 1

    # 0: invalid
    # 1:
    # 2:

    def scaled_grade(self, grade):
        return grade * self.value

    def grade(self, grade):
        if type(grade) in [tuple, list]:
            if grade[1] == 0:
                return grade[0]
            if grade[1] > 1 and grade[1] < 9:
                percentage = (grade[0] + 8-grade[1]) / 8
            else:   
                percentage = grade[0] / grade[1]

        else:
            percentage = grade
        return max(4,  int(round(percentage*8)) - 1)

class Rubric(dict):


    def __init__(self, r, submission, problemset, student=None, title=None,  base=None, parent=None):
        if not r:
            r = {'title': 'Rubric', 'sequence': 0, 'requirement_type': 'OPTIONAL', 'item_id': '', 'problems': {}, 'num_required': 0, 'parent': None, 'grades': {}, 'overall': {}, 'timestamp': ''}
        
        
        super().__init__(r)
        self.problemset = problemset
        
        if submission and not student:
            student = submission.student
        self.student = student
        self.submission = submission

        if parent and not base:
            base = parent.base
        self.parent = parent
        self.base = base or self

        self['title'] = title
        self.problemsets = {}
        
        if problemset:
            self['title'] = problemset.get_title()
            self.setdefault('sequence', 0)
            self.setdefault('requirement_type', 'REQUIRED')
            self['item_id'] = problemset.id_string()
            self.setdefault('problems', {})
            self['num_required'] = problemset.num_required
            self.setdefault('grades', {})
            self.setdefault('comments', [])
            self.base.problemsets[problemset.id_string()] = self
            self.problemsets[problemset.id_string()] = self
            self['weightings'] = {}
            self.setdefault('avg_method', 'bool')

        self.cur_criterion = None
        self.cur_category = None
        self.cur_problem = None
        self.cur_problemset = self
        
        self.style = """        
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
                .problemset {
                    margin-top: 15px;
                }   
            </style>
            """


    def avg_method(self, method):
        if self.cur_problem:
            self.cur_problem['avg_method'] = method
        else:
            self['avg_method'] = method
        return self

    def problemset_exists(self, psitem_id):
        if self.get_problemset(psitem_id):
            return True
        return False

    def problem(self, psitem=None, psitem_id=None):
        ps = None

        # clear all current_*'s with rubric.problem()
        if not psitem and not psitem_id:
            self.cur_problem = None
            return self.criterion()
        
        if not psitem_id:
            psitem_id = psitem.id_string()
        
        # clear current_*'s if this rubric's parent problemset is called with rubric.problem()
        if self['item_id'] == psitem_id:
            return self.problem()

        # handle added problemsets
        if psitem_id.startswith('ps-'):
            ps = self.get_problemset(psitem_id)
            if not ps:
                item_details = {
                    'item_id': psitem_id,
                    'title': psitem.get_title(),
                    'sequence': psitem.sequence,
                    'requirement_type': psitem.requirement_type.name,
                    'comfort_level': psitem.comfort_level.name,
                    'avg_method': 'bool',
                    'grades': {},
                }

                # create a new rubric to be nested for the added problemset and add it to the base problemsets for retrieval of rubric
                ps = Rubric(item_details, self.submission, psitem.nested_problemset, parent=self)
                self.base.problemsets[psitem_id] = ps
                
                # copy problems over to item_details for retrieval during scoring & reporting
                item_details['problems'] = self.base.problemsets[psitem_id]['problems']

                # add the item details only to the 'problems' list (adding the rubric here would create circular dependency)
                self['problems'][psitem_id] = item_details
        
        # handle added problems
        else:
            if psitem_id not in self['problems']:
                self['problems'][psitem_id] = {
                    'item_id': psitem_id,
                    'title': psitem.get_title(),
                    'sequence': psitem.sequence,
                    'requirement_type': psitem.requirement_type.name,
                    'comfort_level': psitem.comfort_level.name,
                    'grades': {},
                    'criteria': {},
                    'avg_method': getattr(psitem.target(), 'avg_method', None) or 'bool'
                }                       
        
        # set current problem for chaining method calls i.e. rubric.problem(psitem).criterion('style')
        self.cur_problem = self['problems'][psitem_id]        



        # sort self['problems'] by sequence
        # self['problems'] = dict(sorted(self['problems'].items(), key=lambda x: x[1]['sequence']))

        # return nested problemset if called
        if ps:
            return ps
        return self

    def coursework(self, cw_rubric):
        cw_rubric.total_scores()
        self.cur_problem['grades'] = cw_rubric['grades']
        self.cur_problem['overall'] = cw_rubric['overall']
        self.cur_problem['problems'] = cw_rubric['problems']
        self.base.problemsets[self.cur_problem['item_id']] = cw_rubric
        return self

    def criterion(self, criterion_title=None, max_points=None, criterion_num=None):
        # clear all current_*'s with rubric.criterion() (or cascaded from rubric.problem())
        self.cur_criterion = None
        if not criterion_title and not criterion_num: 
            return self.category()

        # find and set current cr   iterion based on criterion_num
        if criterion_num != None:
            for criterion in self.cur_problem['criteria'].values():
                if criterion['sequence'] == criterion_num:
                    self.cur_criterion = criterion
        # or arbitrarily number criteria as they are added from the autograder
        else:
            criterion_num = len(self.cur_problem['criteria']) + 1
        

        # find, create or update the criterion based on criterion_title
        if criterion_title:
            # find and set current criterion based on criterion_title
            if not self.cur_criterion:
                if criterion_title in self.cur_problem['criteria']:
                    self.cur_criterion = self.cur_problem['criteria'][criterion_title]
            
            # create new criterion
            if not self.cur_criterion:
                self.cur_problem['criteria'][criterion_title] = {'title': criterion_title, 'grading_categories': [], 'score': -1, 'max_points': max_points or 1, 'grades': {}, 'sequence': criterion_num}
                self.cur_criterion = self.cur_problem['criteria'][criterion_title]

            # update existing criterion
            else:
                self.cur_criterion['title'] = criterion_title
                self.cur_criterion['max_points'] = max_points or self.cur_criterion['max_points']
                self.cur_criterion['sequence'] = criterion_num or self.cur_criterion['sequence']

        if not self.cur_criterion:
            raise Exception(f"Could not find or create criterion #{criterion_num} with title {criterion_title}")

        # sort criteria by sequence
        self.cur_problem['criteria'] = dict(sorted(self.cur_problem['criteria'].items(), key=lambda x: x[1]['sequence']))

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
    
    def weight(self, weight):
        self['weightings'].setdefault(self.cur_criterion['title'], {}) 
        if self.cur_category:
            self['weightings'][self.cur_criterion['title']][self.cur_category.name] = weight
        else:
            self['weightings'][self.cur_criterion['title']]['all'] = weight
        return self

    def score(self, input_score=None, max_points=None):
        if input_score is not None and max_points is not None:
            self.cur_criterion['score'] = input_score
            self.cur_criterion['max_points'] = max_points

        elif input_score is not None and self.cur_criterion.get('max_points'):
            self.cur_criterion['score'] = input_score

        return self.cur_criterion['score']
    
    def     overall(self, input_problem=None):
        if not input_problem:
            problem = self
        else:
            problem = input_problem
        overall = {}
        if problem['avg_method'] == 'bool':
            for category, grades in problem['grades'].items():  
                overall[category] = bool_avg(grades, problem.get('num_required'))
        if problem['avg_method'] == 'mean':
            for category, grades in problem['mean_grades'].items():
                overall[category] = bool_avg(grades['score'])
        return overall
    
    def overall_int(self):
        overall = 0
        for category, grade in self['overall'].items():
            overall += GradingCategory[category].scaled_grade(bool_avg([grade], self['num_required']))
        if overall < 1000:
            overall += 1000
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

    def get_problemset(self, psitem_id):
        if psitem_id == self['item_id']:
            return self
        if psitem_id in self.base.problemsets:
            return self.base.problemsets[psitem_id]
        if psitem_id in self.problemsets:
            return self.problemsets[psitem_id]
        for problemset_id, problemset in self.problemsets.items():
            if problemset_id == self['item_id']:
                continue
            ps = problemset.get_problemset(psitem_id)
            if ps:
                return ps
        return None

    def total_scores(self, force=False):
        if not force and self['grades'] and self['overall'] and not [p for p in self['problems'].values() if not p['overall'] and not p['grades']]:
            return self
        num_required = self['num_required']
        num_completed = 0
        choice_grades = {}
        optional_grades = {}
        self['grades'] = {}

        for problem_id, problem in self['problems'].items():
            problem['mean_grades'] = {}
            problem['grades'] = {}
            if problem_id.startswith('cw-'):
                cw = self.get_problemset(problem_id)
                problem['grades'] = cw['grades']
                problem['overall'] = cw['overall']
            if problem_id.startswith('ps-'):
                ps = self.get_problemset(problem_id)
                if not ps:
                    logger.warning(f"Problemset {problem_id}-{problem['title']} not found. Removing from 'problems'")
                    problem = {}
                    continue
                ps.total_scores(True)
                problem['grades'] = ps['grades']
                problem['overall'] = ps['overall']
            else:
                for criterion_title, criterion in problem['criteria'].items():
                    for category in criterion['grading_categories']:
                        # if criterion_title in self['weightings'].keys():
                        #     if category in self['weightings'][criterion_title].keys():
                        #         cat_weight = self['weightings'][criterion_title][category]
                        #     elif 'all' in self['weightings'][criterion_title].keys():
                        #         cat_weight = self['weightings'][criterion_title]['all']
                        #     else:
                        #         cat_weight = 1
                        
                        # adjust running total of scores for mean average
                        problem.setdefault('mean_grades', {})
                        problem['mean_grades'].setdefault(category, {"earned_points": 0, "max_points": 0})
                        problem['mean_grades'][category]['earned_points'] += max(criterion['score'], 0)
                        problem['mean_grades'][category]['max_points'] += criterion['max_points']
                        
                        cat = GradingCategory[category]

                        # calculate 8-point scale score for criterion
                        g = cat.grade((criterion['score'], criterion['max_points']))

                        # round up a 7 (B) to an 8 (A) if this is a "more comfortable" (harder) problem
                        if problem['comfort_level'] in ["MORE", "MOST"] and g == 7:
                            g += 1
                        criterion['grades'][category] = [g]
                        problem.setdefault('grading_categories', [])
                        problem['grading_categories'].append(category)

                        problem.setdefault('avg_grades', [])
                        problem['avg_grades'].append(g)
                        
                    self.combine_grades(criterion['grades'], problem['grades'])
                for category, grades in problem['mean_grades'].items():
                    mg = GradingCategory[category].grade((grades['earned_points'], grades['max_points']))
                    if problem['comfort_level'] in ["MORE", "MOST"]:
                        mg += 1
                    grades['score'] = [mg]
            problem['overall'] = self.overall(problem)
            if problem['requirement_type'] == 'REQUIRED':
                self.combine_grades(problem['overall'], self['grades'])
                num_completed += 1
            elif problem['requirement_type'] == 'CHOICE':
                choice_grades[problem_id] = problem
            elif problem['requirement_type'] == 'OPTIONAL':
                optional_grades[problem_id] = problem
        self['problems'] = {k: v for k, v in self['problems'].items() if v}

        while num_completed < num_required:
            best_problem = self.best_problem(choice_grades)
            self.combine_grades(best_problem.get('overall', {}), self['grades'])
            num_completed += 1

        overall = self.overall()
        for problem_id, problem in optional_grades.items():
            for category, score in problem.get('overall', {}).items():
                if score > overall.get(category, 0):
                    self.combine_grades({category: score}, self['grades'])
                    overall = self.overall()

        self['overall'] = overall
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

    def html_grades_oneline(self, grades, required=True):

        return ", ".join([f"{k}: {lettergrade(v, required)}" for k, v in grades.items()]) 
        # return f"{','.join([lettergrade(g, required) for g in grades.values()])} ({', '.join(list(set(k for k in grades.keys())))})"

    def html_problem(self, problem, requirement_type):
        grades = [g for g in problem["grades"].values()]
        requirement_type = problem["requirement_type"]        
        html_content = f"<li class='{self.html_grade_class(grades, requirement_type)}'> {sum([0 for i in [problem['sequence']] if i is None] + [i for i in [problem['sequence']] if i is not None ])}. {problem['title']}:  ({problem['comfort_level']})"
        html_content += "(" + self.html_grades_oneline(problem['overall'], requirement_type=='REQUIRED') + ")"
        p_id = problem['item_id']
        html_content += f'<ul problem_id="{p_id}" class="rubric criteria">'
        for criterion, grade in problem['criteria'].items():
            grade_class = self.html_grade_class([v for v in grade['grades'].values()], requirement_type)
            required = requirement_type == 'REQUIRED'
            if grade['max_points'] > 1:
                html_content += f"<li onclick='override_score(this, {grade['score']}, {grade['max_points']}, {html.escape(grade['title'])});' class='{grade_class}'> {html.escape(grade['title'])}: {grade['score']}/{grade['max_points']} = {self.html_grades_oneline(grade['grades'], required)}"
            else:
                html_content += f"<li onclick='override_score(this, {grade['score']}, {grade['max_points']}, {html.escape(grade['title'])});' class='{grade_class}'> {html.escape(grade['title'])}: {grade['score']}/{grade['max_points']} ({', '.join(k for k in grade['grades'].keys())})"
            
            # html_content += self.html_grades(grade['grades'], requirement_type)
            html_content += '</li>'
        html_content += '</ul></li>'
        return html_content


    def html_problemset(self, problemset, requirement_type, level):
        grades = [g for g in problemset["grades"].values()]
        requirement_type = problemset["requirement_type"]
        html_content = ""
        ps_id = problemset['item_id']
        if int(problemset['sequence']) > 0:
            html_content += f"<ul problemset_id='{ps_id}'><li class='{self.html_grade_class(grades, requirement_type)} problemset'> {int(problemset['sequence'])}. {problemset['title']}"
        
            html_content += " (" + self.html_grades_oneline(problemset['overall']) + ")"
        html_content += f'<ul class="rubric" problemset_id="{ps_id}">'
        for problem_id, problem in problemset['problems'].items():
            if problem_id.startswith("ps-"):
                html_content += self.html_problemset(problem, requirement_type, level+1)
            else:
                html_content += self.html_problem(problem, requirement_type)

        html_content += '</ul>'
        if int(problemset['sequence']) > 0:
            html_content += "</li></ul>"

        return html_content
    
    def html_grades_overall(self, grades, requirement_type):
        html_content = '<ul class="rubric grades">'
        for category, grade in grades.items():
            grade_class = self.html_grade_class(grade, requirement_type)
            html_content += f"<li class={grade_class}> {category}:  {lettergrade(grade)}</li>"
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
            elif int(g) < 7 and int(g) > 4:
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

    def html(self, style=True):
        if not self['problems']:
            return ""
        if style:
            html_content = self.style
        else:
            html_content = ""
        html_content += "<div class='card'>"
        html_content += "<h1 class='card-header'>RUBRIC: " + self['title'] + "</h1><div class='card-body'>"
        html_content += "<h3>Overall</h3>"
        html_content += self.html_grades_overall(self['overall'], self['requirement_type'])
        html_content += "<h3>Criteria</h3>"
        html_content += self.html_problemset(self, 'REQUIRED', 2)
        html_content += "<h3>Comments</h3>"
        for itemid, problemset in self.base.problemsets.items():
            html_content += self.html_comments(problemset['comments'])

        html_content += f"<br><p>Updated {self.get('timestamp', '?'*10)}</p></div></div>"

        return html_content
    
    def html_ul_from_list(self, l):
        html_content = "<ul>"
        for item in l:
            if type(item) in [list, tuple, set]:
                html_content += self.html_ul_from_list(item)
            elif type(item) is dict:
                html_content += self.html_ul_from_dict(item)
            else:
                html_content += f"<li>{html.escape(str(item))}</li>"
        html_content += "</ul>"
        return html_content

    def html_ul_from_dict(self, d):
        html_content = "<ul>"
        for title, item in d.items():
            html_content += f"<li><strong>{html.escape(title)}</strong>:"
            if type(item) in [list, tuple, set]:
                html_content += self.html_ul_from_list(item) + "</li>"
            elif type(item) is dict:
                html_content += self.html_ul_from_dict(item) + "</li>"
            else:
                html_content += f" {html.escape(str(item))}</li>"
        html_content += "</ul>"
        return html_content


    def html_comments(self, comments=None):
        html_content = "<ul class='comments'>"
        for comment in self['comments']:
            if type(comment) in [list, tuple, set]:
                html_content += "<li>" + self.html_ul_from_list(comment) + "</li>"
            elif type(comment) is dict:
                html_content += "<li>" + self.html_ul_from_dict(comment) + "</li>"
            else:
                html_content += f"<li>{html.escape(str(comment))}</li>"
        return html_content + "</ul>"



        for comment in self['comments']:
            if type(comment) in [list, tuple, set]:
                for c in comment:
                    html_content += self.html_from_list(comment)

    # def html_comments(self, comments, new_ul=True, new_li=False):
    #     html_content = ""
    #     if type(comments) in [list, tuple, set]:
    #         for comment in comments:
    #             html_content = self.html_comments(comment, False, True)
    #     elif type(comments) is dict:
    #         for title, comment in comments.items():
    #             if type(comment) not in [list, tuple, set, dict]:
    #                 html_content += f"<strong>{html.escape(title)}</strong>: {html.escape(str(comment))}"
    #             else:
    #                 html_content += f"<strong>{html.escape(title)}</strong>: {self.html_comments(comment, True, True)}"
    #     else:
    #         html_content += html.escape(str(comments))
    #     if new_li:
    #         html_content = "<li>" + html_content + "</li>"
    #     if new_ul:
    #         html_content = "<ul class='rubric comments'>" + html_content + "</ul>"
    #     return html_content

    def md(self):
        return html.unescape(markdownify.markdownify(self.html(style=False)))
    
    def comment(self, comment=None, overwrite=False):
        if overwrite or not comment:
            self['comments'] = []
        if comment not in self['comments']:
            self['comments'].append(comment)

class AutoGrader():
    def __init__(self, problem, categories=None):
        if not categories:
            self.grading_categories = ["Engagement", "Process", "Product", "Expertise"]
        self.problem = problem
        self.projectrepo = None
        if problem.autograder:
            self.grader = getattr(self, problem.autograder)
        else:
            self.grader = self.no_grader

    def __str__(self):
        return self.grader.__name__

    def grade(self, rubric):
        rubric.avg_method(self.problem.avg_method)
        return self.grader(rubric)

    def submitted_anything(self, rubric):
        if [a for a in rubric.submission.attachments if a.id != rubric.submission.rubric_doc_id and a.student_created()]:
            rubric.criterion('completion').category('ENGAGEMENT').score(1, 1)
        else:
            rubric.criterion('completion').category('ENGAGEMENT').score(0, 1)

        return rubric

    def no_grader(self, rubric):
        return {}

    def submit50(self, rubric):
        rubric.criterion('style50').category('PRODUCT').score(0, 1)
        rubric.criterion('check50').category('EXPERTISE').score(0, 1)
        
        problemsubmission = rubric.submission.student.get_submission_for_problem(self.problem)

        if problemsubmission:
            rubric.criterion('style50').category('PRODUCT').score(problemsubmission.style50_score, 1)
            rubric.criterion('check50').category('EXPERTISE').score(problemsubmission.checks_passed, problemsubmission.checks_run)
            rubric.student.set_github_username(problemsubmission.github_username)
        return rubric
    
    def github_account_profile(self, rubric):
        repo = self.repo(rubric)
        repo.md_init()
        
        rubric.criterion('correctly named').category('PRODUCT').score(int(repo.is_profile_repo()), 1)
        rubric.criterion('submitted link leads to profile page').category('PRODUCT').score(int(repo.submitted_link_to_profile()), 1)

        rubric.criterion('includes a link').category('EXPERTISE').score(int(len(repo.md_elements['links']) > 0), 1)
        rubric.criterion('includes an image').category('EXPERTISE').score(int(len(repo.md_elements['images']) > 0), 1)

        num_md_used = repo.num_md_elements_used(excluded_elements=['images', 'links'])
        rubric.criterion('includes 4 other types of formatting').category('EXPERTISE').score(min(4, num_md_used), 4)

        rubric.comment({"Elements used": repo.md_elements_used()})
        return rubric

    @runtimer
    def website_html(self, rubric):
        repo = self.repo(rubric)
        repo.website_init()
        rubric.comment(repo.html_stat_dict())
        if repo.stats['html_count'] == 0:
            html_count = 1
        else:
            html_count = repo.stats['html_count']
        criteria = {
                    "Exactly 1 opening `<html>` tag on each page": round(repo.stats['html_tags'] / html_count, 1), 
                    "No content after closing `</html>` tag on each page": round(repo.stats['nojunk'] / html_count, 1), 
                    "Exactly 1 `<head>`...`</head>` section on each page": round(repo.stats['head_tag'] / html_count, 1), 
                    "Exactly 1 `<title>`...`</title>` on each page": round(repo.stats['title_tag'] / html_count, 1), 
                    "Exactly 1 `<body>`...`</body>` on each page": round(repo.stats['body_tag'] / html_count, 1), 
                    "At least one heading (`<h1>`...`</h1>`, `<h2>`...`</h2>`, etc.)  on any page": int(bool(repo.stats['heading_tag'])),
                    "At least 1 `<p>`...`</p>` on any page": int(bool(repo.stats['p_tag'])),
                    "List (`<ul>` or `<ol>` and `<li>`) or table on any page": int(bool(repo.stats['list_tag'])),
                    "At least one image on each page": int(bool(repo.images_per_page)),
                    "The height or width attribute is used on any image": int(bool(repo.images_per_page)), 
                    "External style sheet, `<style>`...`</style>` section, or inline style (`style=""`) on each page": round(repo.stats['css'] / html_count, 1), 
                }

        self.expertise_from_dict(rubric, criteria)

        return rubric



    def expertise_from_dict(self, rubric, d):
        for criteria, score in d.items():
            maxpoints = 1
            if type(score) in [tuple, list]:
                earnedpoints = score[0]
                maxpoints = score[1]
            else:
                earnedpoints = score
            rubric.criterion(criteria).category('EXPERTISE').score(earnedpoints, maxpoints)
        return rubric

    @runtimer
    def website_css(self, rubric):
        repo = self.repo(rubric)
        repo.website_init()
        criteria = {
                    "External style sheet is linked to at least one page": int(bool(repo.stats['css'])), 
                    "CSS Classes are defined and used on any page": int(bool(repo.stats['css'])), 
                    "CSS tag/element selectors are defined and used on any page": int(bool(repo.stats['css'])), 
                    "Inline CSS AND/OR ID selectors are used on any page": int(bool(repo.stats['inline_css'] or repo.stats['pages_with_ids'])), 
                    "CSS attribute background or background-color in any style rule": int(repo.stats['background_rule']), 
                    "CSS attribute border is used in any style rule": int(repo.stats['border_rule']), 
                    "CSS font attributes are used (font-family, font-size, color, and/or other font properties) in any style rule": int(repo.stats['font_rule']), 
                }
        
        return self.expertise_from_dict(rubric, criteria)

    @runtimer
    def website_structure(self, rubric):
        repo = self.repo(rubric)
        repo.website_init()
        criteria = {
                        "`index.html` exists": int(repo.file_exists('index.html')), 
                        "External style sheet `.css` file exists": int(repo.file_exists('*.html')), 
                        "At least 3 `.html` files exist": (min(3, round(repo.count_filetype('.html'))), 3), 
                        "None of the URLs on the site point to locations on the dev's computer (i.e., don't begin with `file://`)": int(bool(repo.valid_links or repo.valid_images) and not bool(repo.local_links)), 
                        "Each page is accessible via an internal link from another page": int(bool(repo.valid_links and repo.pages_linked_internally())), 
                        "At least 1 external link on any page": int(bool(repo.stats['external_link']))
                    }
        
        self.expertise_from_dict(rubric, criteria)
        return rubric





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
    
    # def graded_on_classroom(self, rubric):
    #     if type(owner) is Submission:
    #         score = int0(owner.get_score(mark_draft=False, from_cr=True))
    #         max_score = owner.coursework.cr.get('maxPoints')
    #     else:
    #         owner.maxPoints = owner.cr.get('maxPoints')
    #         score = owner.maxPoints
    #         max_score = score
            
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

    def manual(self, rubric):
        for criterion in self.problem.criteria_by_sequence():
            rubric.criterion(criterion.title, criterion.max_points, criterion.sequence)
            for category in criterion.get_grading_categories():
                rubric.category(category)

            # overwrite unentered scores with zeros (keeping scores already entered)
            if not rubric.score():
                rubric.score(0, criterion.max_points)
        return rubric

    def repo(self, rubric):
        if not self.projectrepo:
            self.projectrepo = ProjectRepo.get(rubric.submission)

        rubric.student.set_github_username(self.projectrepo.username)
        return self.projectrepo
    
    def profile_repo_submitted(self, rubric, livesite=False):
        repo = self.repo(rubric)
        rubric.criterion('Repo exists and is public').category('PRODUCT').score(int(repo.exists()), 1)
        rubric.criterion('Link to repo submitted').category('PRODUCT').score(int(repo.exists()), 1)
        return rubric

    def repo_submitted(self, rubric, livesite=False):
        repo = self.repo(rubric)
        rubric.criterion('Repo exists and is public').category('PRODUCT').score(int(repo.exists()), 1)
        rubric.criterion('Link to repo submitted').category('PRODUCT').score(int(repo.submitted_link_to_repo()), 1)
        return rubric
    
    def website_repo_submitted(self, rubric):
        rubric = self.repo_submitted(rubric)
        rubric.criterion('Link to live site submitted').category('PRODUCT').score(int(self.projectrepo.submitted_link_to_livesite()), 1)
        rubric.criterion("live site is accessible").category("PRODUCT").score(int(validate_target(self.projectrepo.livelink)), 1)
        return rubric


    
    @runtimer
    def classic_computer_stan(self, rubric):
        repo = self.repo(rubric)
        repo.md_init()
        
        rubric.criterion('includes a link').category('EXPERTISE').score(int(len(repo.md_elements['links']) > 0), 1)
        rubric.criterion('includes an image').category('EXPERTISE').score(int(len(repo.md_elements['images']) > 0), 1)

        num_md_used = repo.num_md_elements_used()
        rubric.criterion('includes 7 types of formatting').category('EXPERTISE').score(max(0, num_md_used), 7)

        rubric.comment({"Elements used": repo.md_elements_used()}, overwrite=True)        

        return rubric
    
    def more_than_7_formatting_types(self, rubric):
        repo = self.repo(rubric)
        num_md_used = repo.num_md_elements_used()
        rubric.criterion('includes more than 7 types of formatting').category('EXPERTISE').score(int(bool(num_md_used > 7)), 1)
        rubric.criterion("includes an image in the repository").category('EXPERTISE').score(int(bool(repo.relative_image_links())), 1)

class Page():
    targets_filepath = "targets.json"
    targets = {}

    @classmethod
    @runtimer
    def load_targets(cls):
        if cls.targets:
            return
        if os.path.exists(cls.targets_filepath):
            with open(cls.targets_filepath) as c:
                cls.targets = json.load(c)

    @classmethod
    @runtimer
    def write_targets(cls):
        with open(cls.targets_filepath, 'w', encoding='utf-8') as c:
            c.write(json.dumps(cls.targets, indent=4))

    @classmethod
    @runtimer
    def validate_target(cls, target, page=None, proj=None, force=FORCE_VALIDATE_URLS):
        logger.info("validating " + target)
        target = target.strip()
        if page and not proj:
            proj = page.proj

        r = None
        # link to nowhere
        if not target or target.startswith("#"):
            return r
        #relative link to home folder
        if target == "/":
            r = "relative"
        

            
        # local link
        elif "file://" in target:
            r = "local"
        elif proj and proj.file_exists(target):
            r = "relative"
        # url already been validated
        elif not force and cls.targets.get(target) != None:
            r = cls.targets[target]
        else:
            r = request_url(target)                    
            if r == 404:
                r = False
            elif type(r) is requests.models.Response:
                if r.status_code == 404:
                    r = False
                elif target.startswith("http://") or target.startswith("https://"):
                    r = "external"
                else:
                    r = True
            else:
                if type(r) is requests.exceptions.InvalidURL:
                    r = False
                # elif input("Check manually. Is it valid? (y/n) ").lower() in ["y", "yes"]:
                if target.startswith("http://") or target.startswith("https://"):
                    r = "external"
                else:
                    r = False
                # else:
                #     r = False
                    

        if target not in cls.targets or cls.targets[target] != r:
            cls.targets[target] = r
        # if proj:
        #     if target not in proj.targets:
        #         proj.targets.append(target)

        return r

    def __init__(self, page, proj):
        self.page = page
        self.proj = proj
        self.soup = self.page['soup']
        self.html_tags = 0
        self.nojunk = 0
        self.head_tag = 0
        self.body_tag = 0
        self.title_tag = 0
        self.heading_tag = 0
        self.p_tag = 0
        self.list_tag = 0
        self.comment_tag = 0
        self.inline = 0
        self.style_tag = 0
        self.external_link = 0
        self.div_tag = 0
        self.linked_sheets = []
        self.external_sheet = 0
        self.inline_style_rules = []
        self.classes_used = []
        self.ids_used = []
        self.internal_style_rules = []
        self.all_tags = []
        self.bootstrap = 0
        self.script  = 0
        self.targets = []
        self.image_targets = []
        self.valid_links = []
        self.broken_links = []
        self.local_links = []
        self.external_links = []
        self.relative_links = []
        self.valid_images = []
        self.broken_images = []
        self.possibly_broken_targets = []
        self.js_all = ""
        self.find_tags()
        self.find_images()
        self.find_links()
        self.validate_targets()
        self.html_stats()
        self.css_stats()
        self.js_stats()

    @runtimer
    def js_stats(self):
        scripts = self.soup.find_all('script')
        if len(scripts) > 0:
            self.script = 1
        for script in scripts:
            self.js_all += "\n" + "\n".join(script.contents)

    @runtimer
    def find_tags(self):
        logger.info("finding tags")
        for tag in self.page['soup'].find_all():
            self.all_tags.append(str(tag.name))

    @runtimer
    def find_images(self):
        self.images = self.soup.find_all('img')
        self.proj.num_images += len(self.images)
        for img in self.images:
            target = img.get('src')
            if target:
                self.image_targets.append(target)
            try:
                h = img.height
                self.proj.heightwidth = True
            except KeyError:
                try:
                    w = img.width
                    self.proj.heightwidth = True
                except KeyError:
                    pass
    @runtimer        
    def find_links(self):

        links = self.page['soup'].find_all('a')

        for link in links:
            target = link.get('href')
            if target:
                self.targets.append(target)
            


    @runtimer
    def validate_targets(self):
        self.targets = list(set(self.targets))
        self.image_targets = list(set(self.image_targets))
        for target in self.targets:
            validity = Page.validate_target(target, self)
            # 18 At least 1 external link is included
            if validity == False and target not in self.broken_links:
                self.broken_links.append(target)
            elif validity == True and target not in self.valid_links:
                self.valid_links.append(target)
            elif validity == "local" and target not in self.local_links:
                self.local_links.append(target)
            elif validity == "relative" and target not in self.relative_links:
                self.relative_links.append(target)
            elif validity == "external" and target not in self.external_links:
                self.external_links.append(target)
                self.external_link = 1
            else:
                if target not in self.possibly_broken_targets:
                    self.possibly_broken_targets.append(target)

        for target in self.image_targets:
            validity = Page.validate_target(target, self)
            if validity in [True, "relative", "external"] and target not in self.valid_images:
                self.valid_images.append(target)
            elif validity in [False, "local"] and target not in self.broken_images:
                self.broken_images.append(target)
            else:
                if target not in self.possibly_broken_targets:
                    self.possibly_broken_targets.append(target)

    @runtimer
    def html_stats(self):
        # 6 Exactly 1 opening <html> tag
        if len(self.soup.find_all('html')) == 1:
            self.html_tags = 1
        if len(self.soup.find_all('script')) > 0:
            self.script = 1
        # 7 No content after closing </html> tag
        f = Path(self.page['filename']).read_text()
        if f.replace("\n", "").strip()[-len("</html>"):] == "</html>":
                self.nojunk = 1
        # 8 Exactly 1 <head>...</head> section
        if len(self.soup.find_all('head')) == 1:
            self.head_tag = 1
        # 9 Exactly 1 <title>...</title>
        if len(self.soup.find_all('title')) == 1:
            self.title_tag = 1
        # 10 Exactly 1 <body>...</body>
        if len(self.soup.find_all('body')) == 1:
            self.body_tag = 1
        # 11 At least one heading (<h1>...</h1>, <h2>...</h2>, etc.)
        headings = ["h1", "h2", "h3", "h4", "h5", "h6"]
        for h in headings:
            if len(self.soup.find_all(h)) > 0:
                self.heading_tag = 1
                break
        # 12 At least 1 <p>...</p>
        if len(self.soup.find_all('p')) > 0:
            self.p_tag = 1
        # 13 List (<ul> or <ol> and <li>) or table
        lists = ["ul", "ol", "table"]
        for l in lists:
            if len(self.soup.find_all(l)) > 0:
                self.list_tag = 1
                break
        # 14 Comments (<!-- this is a comment -->)
        comments = self.soup.findAll(text=lambda text:isinstance(text, Comment))
        if len(comments) > 0:
            self.comment_tag = 1
        # 30 At least one <div>...</div>
        divs = self.soup.find_all('div')
        if len(divs) > 0:
            for tag in divs:
                if 'style' in tag.attrs or 'class' in tag.attrs or 'id' in tag.attrs:
                    self.div_tag = 1
                    break

    @runtimer
    def css_stats(self):
        # CSS
        # 15 External style sheet, <style>...</style> section, or inline style (style="")
        for tag in self.soup():
            if 'style' in tag.attrs:
                self.inline = 1
                self.inline_style_rules.append(tag.get('style'))
            if 'class' in tag.attrs:
                for c in tag.get('class', []):
                    self.classes_used.append(c)
            if 'id' in tag.attrs:
                self.ids_used.append(tag.get('id'))
        style_sections = self.soup.find_all('style')
        if len(style_sections) > 0:
            self.style_tag = 1
            for s in style_sections:
                self.internal_style_rules.append(s.get_text())
        self.linked_sheets = self.soup.find_all('link')
        if len(self.linked_sheets) > 0:
            for l in self.linked_sheets:
                for c in self.proj.filelist['.css']:
                    if c in l.get('href', ""):
                        self.external_sheet = 1
                if "bootstrap" in l.get("href", ""):
                    self.bootstrap = 1

class ProjectRepo():
    register = {}

    @classmethod
    def get(cls, submission):
        r = cls.register.get(submission.id)
        if r and r.timestamp > datetime.datetime.now() - datetime.timedelta(minutes=30):
            return cls.register[submission.id]
        return cls(submission)

    STUDENTWORK_DIR = 'studentwork'
    @runtimer
    def __init__(self, submission, force_links=False):
        self.submission = submission
        self.coursework_foldername = submission.coursework.filename()
        self.submission_foldername = submission.filename()
        self.coursework_path = self.rename_folder(self.coursework_foldername, self.STUDENTWORK_DIR)
        self.repo_path = self.rename_folder(self.submission_foldername, self.coursework_path, False)
        self.urls = submission.attachment_urls()
        self.parse_github_urls(force_links=force_links)
        self.repo = self.update_repo()
        self.filelist = self.list_files()  
        self.js_all = ""
        self.register[submission.id] = self
        self.stats = {}
        self.timestamp = datetime.datetime.now()

    def md_elements_used(self, excluded_elements=[]):
        return [e for e in self.md_elements['elements_used'] if e not in excluded_elements]

    def num_md_elements_used(self, excluded_elements=[]):
        return len(self.md_elements_used(excluded_elements))

    def repo_exists(self):
        if self.repo:
            return True
        return False

    def rename_folder(self, new_foldername, parent_folder, create=True):
        folder_id = new_foldername.split("---")[-1]
        for folder in os.walk(parent_folder):
            if folder[0].endswith(folder_id):
                os.rename(folder[0], os.path.join(parent_folder, new_foldername))
                return os.path.join(parent_folder, new_foldername)
        if create:
            os.mkdir(os.path.join(parent_folder, new_foldername))
        return os.path.join(parent_folder, new_foldername)

    def md_init(self):
        self.md_elements = self.find_md_elements()
 
    def website_init(self):
        Page.load_targets()
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
        Page.write_targets()

    @runtimer
    def make_pages(self):
        Page.load_targets()
        if not self.filelist['htmlsoup']:
            self.images_per_page = 0
            self.broken_links_percentage = 0
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
            r = None
            if "{" not in rule:
                rule = ""
                continue
            if "@" in rule:
                rule = rule[rule.index("{")+1:]
                continue
            if "." in rule:
                r = rule[rule.index(".")+1:]
                try:
                    self.classes_defined.append(r[:r.index("{")].strip())
                except ValueError:
                    pass
                continue
            if "#" in rule:
                r = rule[rule.index("#")+1:]
                try:
                    self.ids_defined.append(r[:r.index("{")].strip())
                except ValueError:
                    pass
                continue
            self.tag_selectors.append(rule[:rule.index("{")])

        for r in self.inline_style_rules:
            new_r = r.replace('\n', "")
            r = new_r.strip()
        self.classes_used = list(set(self.classes_used))


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
            'numbered_lists': [],
            'footnotes': [],
            'youtube_videos': [],
            'blockquotes': [],
            'emoji': [],
            'tables': []
        }

        for file in filelist:
            with open(file, 'r') as f:
                content = f.read()
                element_contents['tables'].extend(re.findall(r'-{3,}\s*\|\s*-{3,}', content, flags=re.MULTILINE))
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
                element_contents['horizontal_rules'].extend(re.findall(r'\*\*\*(.*)\n', content))
                element_contents['lists'].extend(re.findall(r'^[\*\-\+]\s(.*)', content, flags=re.MULTILINE))
                element_contents['numbered_lists'].extend(re.findall(r'^\d+\.\s(.*)', content, flags=re.MULTILINE))  # Pattern for numbered lists
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
        if self.stats:
            return self.stats
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
        self.css_ids = []
        
        if self.count_filetype('.html') > 0:
            for page in self.pages:
                self.css_ids += page.ids_used
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
        stat.append(f"- css_ids: {[i for i in list(set(self.css_ids)) if i]}")
        stat.append(f"- {self.num_images} valid images: {self.valid_images}")
        stat.append(f"- Broken images: {self.broken_images}")
        stat.append(f"- {len(self.filelist['.html'])} HTML files: {self.filelist['.html_relative']}")
        stat.append(f"- HTMl tags used: {list(set(self.all_tags))}")
        for a, b in {"Valid links": self.valid_links, "Relative targets": self.relative_links, "Local targets": self.local_links, "Broken links": self.broken_links, "Other targets (may or may not be broken)": self.possibly_broken_targets}.items():
            stat.append(f"- {a}: {b}")
        self.stats = stats
        self.stat_string = "  \n" + "  \n".join(stat)
        return stats

    def html_stat_dict(self):
        stat = {"Repository": f"[{self.reponame}]({self.repolink})",
        "Live site": f"[{self.livelink}]({self.livelink})",
        f"{len(self.filelist['.css'])} CSS files": self.filelist['.css_relative'],
        "style rules": self.style_rules,
        "inline style": self.inline_style_rules,
        "classes used": self.classes_used,
        "classes defined": self.classes_defined,
        "css ids": ", ".join(set([i for i in self.css_ids if i])),
        f"{self.num_images} valid images": self.valid_images,
        "Broken images": self.broken_images,
        f"{len(self.filelist['.html'])} HTML files": self.filelist['.html_relative'],
        "HTML tags used": list(set(self.all_tags)),
        "Valid links": self.valid_links, 
        "Relative targets": self.relative_links, 
        "Local targets": self.local_links, 
        "Broken links": self.broken_links, 
        "Other targets (may or may not be broken)": self.possibly_broken_targets
        }

        return stat
    
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
                if 'github.com' not in url.split("/"):
                    continue
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