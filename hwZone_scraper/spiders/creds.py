import datetime
import re

username = 'DisinfoResearch'
password = '27xts79SzpHV8bL!'

test_text = '\nHello \nFrom \t\tThe other side 1253471248 dgmdl'
a = " ".join(test_text.split())
a_digit = re.findall('\d+', a)
print(a_digit, type(a_digit))