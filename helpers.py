from slugify import slugify
from time import sleep
import urllib
from logdef import *
from runtimer import *
from secrets_parameters import *
import datetime
import re
import numpy
import requests
import re
import csv, json
#ChatGPT
def dict_to_html_ul(dictionary):
    if not isinstance(dictionary, dict):
        return str(dictionary)
    html_content = '<ul>'
    for key, value in dictionary.items():
        html_content += '<li class="yesyes">' + str(key) + ": "
        if isinstance(value, dict):
            html_content += dict_to_html_ul(value)  # Recursive call
        else:
            html_content += str(value)
        html_content += '</li>'
    html_content += '</ul>'
    return html_content

def combine_dict(source, target):
    for key, value in source.items():
        if type(value) is dict:
            target.setdefault(key, {})
            target[key] = combine_dict(value, target[key])
        elif type(value) is list:
            target.setdefault(key, [])
            target[key] += value
        else:
            target[key] = value
    return target


def is_valid_domain(s):

    for ext in ["html", "jpeg", "png", "svg", "gif"]:
        if s.endswith(ext):
            return False
    # Regex to check valid
    # domain name.
    regex = "^((?!-)[A-Za-z0-9-]" + "{1,63}(?<!-)\\.)" +"+[A-Za-z]{2,6}"
     
    # Compile the ReGex
    p = re.compile(regex)
 
    # If the string is empty
    # return false
    if (s == None):
        return False
 
    # Return if the string
    # matched the ReGex
    if(re.search(p, s)):
        return True
    else:
        return False




def parse_local_value(key, value, payload):
    if key in ['dueDate', 'dueTime']:
        payload['dueDate'] = datetime_to_cr("date", value)
        payload['dueTime'] = datetime_to_cr("time", value)
        if key == 'dueDate':
            return payload['dueDate']
        if key == 'dueTime':
            return payload['dueTime'] 
    return value

def parse_classroom_value(key, value, cr):
    return value

def datetime_to_cr(output_format, datetime_obj):
    if type(datetime_obj) is str:
        dt = datetime.datetime.strptime(datetime_obj, '%Y-%m-%dT%H:%M:%S') - datetime.timedelta(hours=TIMEZONE_OFFSET)
    if type(datetime_obj) is datetime.datetime:
        dt = datetime_obj
    if output_format == "isoformat":
        return dt.isoformat()
    
    y = dt.year
    m = dt.month
    d = dt.day
    hr = dt.hour - TIMEZONE_OFFSET
    mi = dt.minute

    if output_format == "time":
        return {'hours': hr, 'minutes': mi}
    if output_format == "date":
        return {'day': d, 'month': m, 'year': y}


    


def cr_to_datetime(output_format, cr_date, cr_time=None, offset=False):
        if not cr_date:
            return None
        if type(cr_date) is str:
            converted_date =  datetime.datetime.strptime(cr_date, '%Y-%m-%dT%H:%M:%S') + datetime.timedelta(hours=TIMEZONE_OFFSET).isoformat()
        if type(cr_date) is dict:
            y = cr_date['year']
            m = cr_date['month']
            d = cr_date['day']
            if not y or not m or not d:
                return None
            if cr_time:
                hr = cr_time.get('hours', 23)
                mi = cr_time.get('minutes', 59)
            else:
                hr = 23
                mi = 59
            converted_date = datetime.datetime(y, m, d, hr, mi) + datetime.timedelta(hours=TIMEZONE_OFFSET)
        if type(cr_date) is datetime.datetime:
            converted_date = cr_date + datetime.timedelta(hours=TIMEZONE_OFFSET)
        if output_format == "datetime":
            return converted_date
        elif output_format == "isoformat":
            return converted_date.isoformat()
        return None

def transpose_csv(input_file_path, output_file_path):
    # Read CSV file and transpose the data
    with open(input_file_path, 'r') as input_file:
        reader = csv.reader(input_file)
        data = list(reader)
        transposed_data = list(zip(*data))

    # Write transposed data to CSV file
    with open(output_file_path, 'w', newline='') as output_file:
        writer = csv.writer(output_file)
        writer.writerows(transposed_data)

    print(f"Transposed data has been written to '{output_file_path}'")

def csv_to_markdown(csv_file_path, grades={}, obsidian_links=False):
    # Read CSV file
    with open(csv_file_path, 'r') as file:
        reader = csv.reader(file)
        data = list(reader)

    # Get the maximum number of columns in any row
    max_columns = max(len(row) for row in data)

    # Create the markdown table header
    header = "| " + " | ".join(data[0]) + " |\n"
    header += "|-" + "-|-".join([''] * len(data[0])) + "|\n"

    # Create the markdown table rows
    rows = ""
    for row in data[1:]:
        row += [''] * (max_columns - len(row))  # Add empty cells for missing columns
        rows += "| " + " | ".join(row) + " |\n"

    # Combine the header and rows to form the markdown table
    markdown_table = header + rows

    return markdown_table
# @runtimer
# def validate_target(target, retry=False):
#     logger.info(f"VALIDATING {target}")
#     try:
#         r = urllib.request.urlopen(target)
#         if r.status == 200:
#             return True
#     except Exception as e:
#         if retry or e.code == 404:
#             return False
#         logger.info(e)
#         sleep(5)
#         return validate_target(target, True)
#     return False

def make_content_section(d: dict, title=None):
    section = ""
    if title:
        title = "# {}\n".format(title)
        section += title
    for key in d.keys():
        if not title:
            title = "# {}\n".format(key)
            section += title
        elif type(d[key]) == list:
            section += key + "  \n"
            for item in d[key]:
                section += "- {}  \n".format(item)
        else:
            section += "{}: {}  \n".format(key, d[key])
        

def lettergrade(score, required=True):
    """
    8 A 
    7 B 
    6 C 
    5 D 
    4 F 
    3 Incomplete
    2 Missing
    1 Excused
    0 Ungraded
    """
    maxpoints = 8
    if type(score) is tuple:
        points = score[0]
        maxpoints = score[1]
    elif type(score) is str:
        score = int(score)
    elif type(score) in [int, float]:
        points = score
    elif type(score) is list:
        return ",".join([lettergrade(s, required) for s in score])
    else:
        raise TypeError("score must be tuple, string, or int")
    
    percent = float(points / maxpoints)
    if percent >= .9:
        return "A"
    if percent >= .8:
        return "B"
    if percent >= .7:
        return "C"
    if percent >= .6:
        return "D"
    if not required:
        return "-"
    # if percent >= .5:
    #     return "F"
    # if score[0] == 3:
    #     return "Incomplete"
    # if score[0] == 2:
    #     return "Missing"
    # if score[0] == 1:
    #     return "Excused"
    # if score[0] == 0:
    #     return "Ungraded"
    return "F"

def prettylist(d: dict):
    pl = ""
    if not d:
        return pl

    for key in d.keys():
        pl += key + ":\n"
        for item in d[key]:
            pl += "- [[" + item + "]]\n"
        pl += "\n"
    return pl

def category_abbreviation(c):
    abbreviations = []
    categories = [w.strip() for w in c.split(",")]
    for cat in categories:
        abbreviations.append("".join(word[0:4] for word in cat.split(" "))[:4])

    return ",".join(abbreviations)



def findkey(d:dict, target_keys):
    if not d:
        return None
    if type(target_keys) is list:
        for k in target_keys:
            if k in d.keys():
                return d[k]
    else:
        if target_keys in d.keys():
            return d[target_keys]

    for key in d.keys():
        if type(d[key]) == dict:
            found = findkey(d[key], target_keys)
            if found:
                return found
    return None

def make_filename(name):
    filename = slugify(name, separator="_", lowercase=False, max_length=50, word_boundary=True)
    if name[0] == "_" and filename[0] != "_":
        filename = "_" + filename
    return filename

def int0(x):
    try:
        return int(x)
    except (ValueError, TypeError):
        if x in ["_", "", None]:
            return 0
        raise

def slug_to_foldername(slug):
        slug_arr = slug.split('/')
        slug_arr.reverse()
        if slug_arr[0] == "less" or slug_arr[0] == "more":
            slug_arr = [slug_arr[1]] + [slug_arr[0]] + slug_arr[2:]
        foldername = '/'.join(slug_arr).replace('/', '-').replace('problems', '').replace('main', '')
        return foldername

def bool_avg(input_scores:list, num_required=None, exclude_zero=True):
    scores = [int0(s) for s in input_scores]
    if not scores:
        return None
    if not num_required:
        num_required = len(scores)
    zero_scores = [s for s in scores if s <= 0]
    if zero_scores and exclude_zero:
        nonzero_scores = [s for s in scores if s > 0]
        while len(nonzero_scores) < num_required:
            nonzero_scores.append(0)
        s = bool_avg(nonzero_scores, exclude_zero=False)
        if not s:
            return 0
        s -= scores.count(0)
        if s < 0:
            return 0
        return s
    while len(scores) > num_required:
        scores.remove(min(scores))
    num_exceeds = len([s for s in scores if s == 8])
    meets = not bool([s for s in scores if s < 7])
    insufficient = bool([s for s in scores if s < 5])
    exceeds = meets and num_exceeds
    if exceeds:
        return 8
    if meets:
        return 7
    if not bool([s for s in scores if s < 6]):
        return 6
    if not insufficient: 
        if len([s for s in scores if s < 6]) < len([s for s in scores if s > 5]):
            return 6
        return 5
    if len([s for s in scores if s < 5]) <= len([s for s in scores if s > 4]):
        return 5
    return 4
    
    return round(numpy.mean(scores))

def request_url(url, max_retry=1):
    response = None
    r = requests.Session()
    retry = 0
    while response == None:
        try:
            response = r.get(url, timeout=5)
        except requests.exceptions.MissingSchema as e:
            logger.info(e)
            if not url.startswith("http"):
                if is_valid_domain(url.split("/")[0]):
                    try:
                        response = r.get("https://"+url)
                    except Exception as e:
                        logger.info(e)
                        try:
                            response = r.get("http://"+url)
                        except Exception as e:
                            logger.info(e)
                            return 404
            return 404

        except Exception as e:
            logger.info(e)
            if retry > max_retry:
                return e
            else:
                retry += 1
    return response

@runtimer
def validate_target(target):
    logger.info("validating " + target)
    if not target:
        return False
    
    if os.path.exists("validated_targets.json"):
        with open("validated_targets.json", "r") as f:
            targets = json.load(f)
    else:
        targets = {}

    
    if target in targets.keys():
        if targets[target] == 404:
            r = request_url(target)
        else:
            return True
    else:
        r = request_url(target)
    
    if r and r is not Exception:
        targets[target] = r.status_code
        with open("validated_targets.json", "w") as f:
            json.dump(targets, f)

    if not r or r.status_code == 404 or r is Exception:
        return False
    return True



