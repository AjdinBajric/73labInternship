import spacy
import pandas as pd
import re
import en_core_web_sm
import slate3k as slate


def pdf_to_text(name):
    """
    Returns extracted text from pdf as list of strings.
    Each element of list is one page of pdf document.

    """
    with open('static/LinkedIn/' + name + '.pdf', 'rb') as f:
        extracted_text = slate.PDF(f)
        f.close()

    return extracted_text


def clean_string(text):
    """
    Remove part of text which contains something like this:
        Page 2 of 3\n\n\xa0\n\xa0\n\xa0\n\x0c

    This part does not contain any valuable information, and sometimes occurs wrong answer in the output.
    """

    pdf = text
    end = 0
    result = ""

    expression = r"Page \d of \d\n\n\xa0\n\xa0\n\xa0\n\x0c"

    for match in re.findall(expression, text):  # method `findall` returns all matched words as an array
        word = re.search(match, pdf)  # search returns start and the end of a word
        pdf = pdf[
              word.end():]  # pdf = pdf[word.end():] #search returns result after first match, so on the next
        # iteration text file should be from the end of the word, to the end of a document
        result += text[end:word.start() + end]  # read text from the end of a last word to the start of the new word
        end += word.end()

    return result


def concat_pages(filename):
    """Concatenate pages in one string, and returns that string"""
    cv = pdf_to_text(filename)
    text = ""

    for page in cv:
        text += page

    text = clean_string(text)

    return text


def get_companies(text, expression):
    """
    Function finds start and the end of a pattern, and put those numbers in a list.
    List of those integers is being returned.
    """
    if expression == "present":
        expression = r"\n\n.+\d{1,4}\xa0-\xa0Present\xa0\n"
    elif expression == "past":
        expression = r'\n\n.+\d{1,4}\xa0-\xa0.+\d{1,4}\xa0.+\n'

    keys = []
    pdf = text
    end = 0

    for match in re.findall(expression, text):
        word = re.search(expression, pdf)
        pdf = pdf[word.end():]
        keys.append([word.start() + end, word.end() + end])
        end += word.end()

    return keys


def get_info(start, text):
    """
    This function returns company and title.

    Parameters:
    start (int): Start of a word

    Returns:
    list[str, str]: [Name of the company, Title in that company]

    """

    string = ""
    for i in reversed(range(start)):
        string += text[i]
        if "\n\n" in string[::-1]:  # reverse an array and check for `\n\n`(end of a word) part in the string.
            title = string[::-1].strip()  # remove /n

            string = ""
            for j in reversed(range(i)):
                string += text[j]
                if "\n\n" in string[::-1]:
                    company = string[::-1].strip()
                    return [company, title]


def find_keywords(text):
    """
    This function should find all parts in text that are like this:
        \n\n2 years 11 months\n\n

    If statements fix some inaccuracies of regex.

    Parameters:
    text (string): Text of a pdf

    Returns: matched_words (list): Matched words in list. Those words mustn't be ("less than a year", "2016-2020 (4
    years)") or something like that.
    """

    expression = r'\n\n\d.+\n\n'
    matched_words = []
    nlp = en_core_web_sm.load()
    for match in re.findall(expression, text):
        doc = nlp(match)
        for token in doc:
            if token.lemma_ == "less" or token.lemma_ == "-":
                break
            if token.lemma_ == "year" or token.lemma_ == "month":
                matched_words.append(match)
                break

    return matched_words


def get_dates_below(matched_words, text, past_companies):
    """
    As you can see in the text, after those keywords there are some dates. If you add first N of those
    dates below you should get value which is equal to the keyword. Example:

    Keyword: 2 years 11 months
    Dates below:
    - August 2013 - April 2014 (9 months)
    - June 2011 - August 2013 (2 years 3 months)
    - March 2010 - June 2011 (1 year 4 months)
    - June 2008 - May 2009 (1 year)
    ...

    If you add first two dates, you can realize that the person in that period worked in the same company.

    Parameters:
    matched_words (list): keywords which met the rules

    Returns:
    array (list): dates below keyword
    pom (list): start and the end of dates below keyword

    """

    end = 0
    pdf = text
    array = []
    pom = []
    position_of_keyword = []

    for matched_word in matched_words:
        for match in re.findall(matched_word, text):
            keys = []
            word = re.search(matched_word, pdf)
            pdf = pdf[word.end():]

            keys.append([word.start() + end, word.end() + end])
            position_of_keyword += keys
            end += word.end()

            array.append([text[key[0]:key[1]] for key in past_companies if keys[0][1] < key[1]])
            pom.append([[key[0], key[1]] for key in past_companies if keys[0][1] < key[1]])

    return array, pom, position_of_keyword


def get_period(array):
    """
    Get part of matched words from brackets. Example:

    Matched word:
    '\n\nAugust 2013\xa0-\xa0April 2014\xa0(9 months)\n'
    Output should be:
    (9 months)

    Parameters:
    array (list): list of dates below keyword

    Returns:
    array (list): list of elapsed times between dates

    """

    expression = r'\(.+\)'

    for i in range(len(array)):
        for j in range(len(array[i])):
            word = array[i][j]
            for match in re.findall(expression, word):
                array[i][j] = match

    return array


def get_year_and_month(word):
    """
    Get year and month from preprocessed data.

    Parameters:
    word (string): elapsed times between dates

    Returns:
    (list): Number of years, Number of months
    """
    nlp = en_core_web_sm.load()
    doc = nlp(word)
    month = 0
    year = 0

    for i in range(len(doc)):
        if doc[i].lemma_ == "year":
            year = doc[i - 1]
        if doc[i].lemma_ == "month":
            month = doc[i - 1]
    return [int(str(year)), int(str(month))]


def fix_errors(matched_words, position_of_keyword, text, array, companies):
    for p in range(len(matched_words)):

        target_year = get_year_and_month(matched_words[p])[0]
        target_month = get_year_and_month(matched_words[p])[1]

        month = 0
        year = 0

        string = ""

        # Get name of a company. Name of a company is placed above keyword.
        for i in reversed(range(position_of_keyword[p][0])):
            string += text[i]
            if "\n\n" in string[::-1]:
                cmp = string[::-1].strip()
                break

        for j in range(len(array[p])):

            # Add months and years
            month += get_year_and_month(array[p][j])[1]
            year += get_year_and_month(array[p][j])[0]

            # Check if they are equal to the target_year and target_month
            if year + (month - 1) // 12 == target_year and (month - 1) % 12 == target_month:
                # Change name of a company for all wrong answers
                start = companies.index(matched_words[p].strip())
                companies[start:start + j + 1] = [cmp for i in range(j + 1)]
                break


if __name__ == '__main__':
    # This part is only for testing
    text2 = concat_pages("FaikC")
    present_keywords = get_companies(text2, "present")
    print(present_keywords)
