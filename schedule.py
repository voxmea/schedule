
import os
import sys
import re
from pprint import pprint
import datetime
import dateutil
from dateutil import parser
from glob import glob
import calendar
from collections import namedtuple
import argparse
import textwrap
import codecs, locale

sys.stdout = codecs.getwriter(locale.getpreferredencoding())(sys.stdout) 

argparser = argparse.ArgumentParser(description='Help with scheduling')
argparser.add_argument('inputs', metavar='inputs', type=str, nargs='+',
                       help='input files or input strings')
argparser.add_argument('--start', dest='start', default=datetime.date.today(),
                       help='start date')
argparser.add_argument('--output_html', dest='output_html', action='store_true',
                       default=False, help='ascii codes or html')
args = argparser.parse_args()

class DateSpan:
    begin = None
    duration = None

    def __init__(self, begin, end):
        if type(begin) == datetime.datetime:
            begin = begin.date()
        self.begin = begin
        if type(end) == int:
            end = dateutil.relativedelta.relativedelta(days=+end)
        self.end = end

    def __repr__(self):
        return '[{},{})'.format(self.begin, (self.begin + self.end))

    def overlaps(self, other):
        max_start = max(self.begin, other.begin)
        min_end = min(self.begin + self.end, other.begin + other.end)
        return (min_end - max_start).days > 0

Holiday = namedtuple('Holiday', ['name', 'span'])

class Entry:
    name = None
    short_name = None
    length = None

    def __init__(self, name, length, short_name = name):
        self.name = name.strip()
        self.length = length
        self.short_name = short_name

    def __repr__(self):
        return '{} - {}'.format(self.name, self.length)

def to_span(input_string):
    if '-' in input_string:
        l, r = input_string.split('-', 1)
        try:
            l = parser.parse(l)
            r = parser.parse(r)
        except ValueError, ex:
            print >> sys.stderr, 'WARNING: could not parse holiday line "', hol, ':', line, '"\n', ex
            raise
        return DateSpan(l, dateutil.relativedelta.relativedelta(r, l) + dateutil.relativedelta.relativedelta(days=+1))
    else:
        try:
            begin = parser.parse(input_string)
        except ValueError, ex:
            print >> sys.stderr, 'WARNING: could not parse holiday line "', hol, ':', line, '"\n', ex
            raise
        return DateSpan(begin, dateutil.relativedelta.relativedelta(days=+1))

# get holidays
holidays = []
for hol in glob('*.HOL'):
    for line in open(hol, 'rb').readlines()[1:]:
        line = line.strip()
        if len(line) == 0:
            continue
        parts = line.rsplit(',')
        if len(parts) != 2:
            print >> sys.stderr, 'WARNING: could not parse holiday line "', hol, ':', line, '"'
            continue
        try:
            span = to_span(parts[-1])
            holidays.append(Holiday(name=parts[0], span=span))
        except ValueError, ex:
            continue

# for entry in holidays:
    # print entry



text_input = []
for argv in args.inputs:
    if os.path.exists(argv):
        text_input.append(open(argv, 'rb').read())
    else:
        text_input.append(argv)

text_input = '\n\n'.join(text_input)
text_input = [i.strip() for i in re.split(r'(?m)^\s*$\s*', text_input)]

duration_regex = re.compile(r'(?P<length>\d+)\s+(?P<kind>(weeks?|days?))')
tasks = []
for ti in text_input:
    try:
        desc, duration = ti.rsplit(':', 1)
    except ValueError:
        desc = ti
        duration = '1 day'
    m = duration_regex.match(duration.strip())
    if not m:
        print >> sys.stderr, 'WARNING: could not parse task line; exiting'
        print >> sys.stderr, ti
        print >> sys.stderr, duration
        sys.exit(1)
    parts = m.groupdict()
    parts['length'] = int(parts['length'])
    if parts['kind'].startswith('week'):
        parts['length'] = parts['length'] * 5
        parts['kind'] = 'days'
    try:
        name, short_name = desc.rsplit(':', 1)
    except ValueError:
        name = desc
        short_name = ''
    tasks.append(Entry(name, parts['length'], short_name))

# pprint(tasks)

# today = datetime.date.today()
# one_day = DateSpan(today + dateutil.relativedelta.relativedelta(days=+0), 8)
# two_day = DateSpan(today + dateutil.relativedelta.relativedelta(days=+7), 7)
# print one_day, two_day
# print one_day.overlaps(two_day)

def next_weekday(now):
    while True:
        now = now + dateutil.relativedelta.relativedelta(days=+1)
        if now.weekday() < 5:
            return now

if type(args.start) == str:
    args.start = parser.parse(args.start, fuzzy=True).date()
now = args.start
if now.weekday() >= 5:
    now = next_weekday(now)
for task in tasks:
    begin = None
    end = None
    for day in range(task.length):
        while True:
            masks = [hol for hol in holidays if hol.span.overlaps(DateSpan(now, 1))]
            if any(masks):
                # print 'task was masked', task, masks[0]
                now = next_weekday(now)
            else:
                break
        # print 'scheduled ', task, 'on', now
        if not begin:
            begin = now
        now = next_weekday(now)
        end = now
    task.begin = begin
    task.end = end

blue = '\033[94m'
reset = '\033[0m'
if args.output_html:
    blue = '<font color="blue">'
    reset = '</font>'
for task in tasks:
    half_open_adjustment = dateutil.relativedelta.relativedelta(days=+1)
    cals = []

    cal = calendar.TextCalendar(calendar.SUNDAY)
    text = cal.formatmonth(task.begin.year, task.begin.month)
    regex = re.compile(r'(\b|^){}(\b|$)'.format(task.begin.day))
    m = regex.search(text)
    text = text[:m.start()] + blue + text[m.start():]

    if (task.begin.year == task.end.year) and (task.begin.month == task.end.month):
        regex = re.compile(r'(\b|^|{1}){0}(\b|$|{1})'.format((task.end - half_open_adjustment).day, re.escape(blue)))
        m = regex.search(text)
        if not m:
            print text
            print regex.pattern
            sys.exit(1)
        text = text[:m.end()] + reset + text[m.end():]
        cals.append(text)
    else:
        text = text[:-1] + reset + text[-1:]
        cals.append(text)

        month = task.begin + dateutil.relativedelta.relativedelta(months=+1)
        while (month < task.end) and (month.month != task.end.month):
            text = cal.formatmonth(month.year, month.month)
            regex = re.compile(r'(\b|^)1(\b|$)')
            m = regex.search(text)
            text = text[:m.start()] + blue + text[m.start():-1] + reset + text[-1:]
            month = month + dateutil.relativedelta.relativedelta(months=+1)
            cals.append(text)
        if month.month == task.end.month:
            text = cal.formatmonth(month.year, month.month)
            regex = re.compile(r'(\b|^)1(\b|$)')
            m = regex.search(text)
            text = text[:m.start()] + blue + text[m.start():]

            regex = re.compile(r'(\b|^){}(\b|$)'.format((task.end - half_open_adjustment).day))
            m = regex.search(text)
            text = text[:m.end()] + reset + text[m.end():]
            cals.append(text)

    task.cals = ''.join(cals)


html_header = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Schedule</title>
</head>
<body>
<pre>
'''
if args.output_html:
    print html_header

table = []
for task in tasks:
    name = [''] + textwrap.wrap(task.name, 40)
    cals = task.cals.split('\n')

    lines = max(len(name), len(cals))
    cal_width = max(*[len(re.sub('{}|{}'.format(re.escape(blue), re.escape(reset)), '', l)) for l in cals])
    cal_format = '{{: <{}}}'.format(cal_width)

    date_range = '{} [{},{})'.format(task.short_name, task.begin, task.end)
    print '{: ^80}'.format(date_range)
    print u'\u2500' * 80
    is_blue = False
    for i in range(lines):
        if i < len(cals):
            formatted_cal = cal_format.format(cals[i])
            print formatted_cal,
            actual_len = len(formatted_cal.replace(blue, '').replace(reset, ''))
            if actual_len < cal_width:
                print ' ' * (cal_width - actual_len - 1),
            if l.find(blue) != -1 and l.find(reset) != -1:
                print u'  {}\u2502{} '.format(blue, reset),
                is_blue = False
            elif l.find(blue) == -1 and l.find(reset) != -1:
                print u'  {}\u2502{} '.format(blue, reset),
                is_blue = False
            elif l.find(blue) != -1 and l.find(reset) == -1:
                print u'  \u2502 ',
                is_blue = True
            else:
                print u'  \u2502 ',
        else:
            print cal_format.format(''),
            print u'  \u2502 ',

        if is_blue:
            print reset,
        if i < len(name):
            print '{:<60}'.format(name[i].strip()),
        else:
            print '{:<60}'.format(''),
        if is_blue:
            print blue,

        print ''
    print '\n'

html_footer = '''
</pre>
</body>
</html>
'''
if args.output_html:
    print html_footer



