import_ok = True
print('Testing all imports')
try:
    from PIL import Image
except:
    print('Cannot import Image from pillow')
    import_ok = False

try:
    import six
except:
    print('Cannot import six')
    import_ok = False

try:
    from lxml import etree
except:
    print('Cannot import from lxml')
    import_ok = False

try:
    import numpy
except:
    print('Cannot import numpy')
    import_ok = False

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plot
except Exception as e:
    print(f'Cannot import matplotlib: {e}')
    import_ok = False

try:
    import pytest
except:
    print('Cannot import pytest')
    import_ok = False

try:
    import pandas
    df = pandas.DataFrame()
except:
    print('Cannot import pandas')
    import_ok = False

try:
    import xgboost
    df = pandas.DataFrame()
except:
    print('Cannot import pandas')
    import_ok = False

try:
    from sklearn import metrics
    from sklearn.preprocessing import LabelEncoder
except:
    print('Cannot import from scikit-learn')
    import_ok = False

try:
    from sklearn.preprocessing import LabelEncoder
    import xgboost
    from xgboost.compat import XGBoostLabelEncoder
except:
    print('Cannot import from xgboost')
    import_ok = False

try:
    from scipy import misc
except:
    print('Cannot import from scipy')
    import_ok = False

if not import_ok:
    import sys
    sys.exit(1)

print('All imports worked, huzzah!')
