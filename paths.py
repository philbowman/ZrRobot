import os 
from pprint import pprint
import json

def main(startpath = None):
    if not startpath:
        startpath = "/Users/pil/Library/Mobile Documents/iCloud~md~obsidian/Documents/neu"
    tree = {}
    for root, dirs, files in os.walk(startpath):
        branches = [startpath]
        if root != startpath:
            branches.extend(os.path.relpath(root, startpath).split('/'))

        set_leaf(tree, branches, dict([(d,{}) for d in dirs]+ \
                                    [(f,None) for f in files]))

    with open('paths.json', 'w', encoding='utf-8') as jsonf:
        jsonf.write(json.dumps(tree, indent=4))

def file_structure_dict(startpath):
    tree = {}
    for root, dirs, files in os.walk(startpath):
        branches = [startpath]
        if root != startpath:
            branches.extend(os.path.relpath(root, startpath).split('/'))

        set_leaf(tree, branches, dict([(d,{}) for d in dirs]+ \
                                    [(f,None) for f in files]))
    return tree

def set_leaf(tree, branches, leaf):
    """ Set a terminal element to *leaf* within nested dictionaries.              
    *branches* defines the path through dictionnaries.                            

    Example:                                                                      
    >>> t = {}                                                                    
    >>> set_leaf(t, ['b1','b2','b3'], 'new_leaf')                                 
    >>> print t                                                                   
    {'b1': {'b2': {'b3': 'new_leaf'}}}                                             
    """
    if len(branches) == 1:
        tree[branches[0]] = leaf
        return
    if not tree.get(branches[0]):
        tree[branches[0]] = {}
    set_leaf(tree[branches[0]], branches[1:], leaf)

if __name__ == '__main__':
    main()


