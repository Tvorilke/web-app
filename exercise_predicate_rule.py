import spacy
import enchant
import pymorphy3
import sqlite3
import traceback
import sys

morph = pymorphy3.MorphAnalyzer()
d = enchant.Dict("ru")
nlp = spacy.load('ru_core_news_sm')


def get_rows():
    try:
        sqlite_connection = sqlite3.connect('../DB/web_app.db')
        cursor = sqlite_connection.cursor()
        sqlite_select_query = """SELECT * from sentences_markup"""
        cursor.execute(sqlite_select_query)
        records = cursor.fetchall()
        print("Всего строк:  ", len(records))
        for row in records:
            sent_id = row[0]  # 2
            sent_text = row[1]  # Формирование тематики исследования для молодого ученого всегда является трудоемкой
            # задачей.
            sent_markup = row[2]  # (Формирование, NOUN, nsubj, является, [тематики], 0, 12); (тематики, NOUN, nmod,
            # Формирование, [исследования], 13, 21); (исследования, NOUN, nmod, тематики, [ученого], 22, 34); (для,
            # ADP, case, ученого, [], 35, 38); (молодого, ADJ, amod, ученого, [], 39, 47); (ученого, NOUN, nmod,
            # исследования, [для, молодого], 48, 55); (всегда, ADV, advmod, является, [], 56, 62); (является, VERB,
            # ROOT, является, [Формирование, всегда, задачей, .], 63, 71); (трудоемкой, ADJ, amod, задачей, [], 72,
            # 82); (задачей, NOUN, xcomp, является, [трудоемкой], 83, 90); (., PUNCT, punct, является, [], 90, 91)
            text_theme = row[3]
            data = task_rule_gen(sent_text, sent_markup, sent_id, text_theme)
            if data:
                try:
                    sqlite_insert_query = """INSERT INTO exercises
                                            (type, exer_text, words_to_mod, answer, hint, sent_id, text_theme) VALUES(?, ?, ?, ?, ?, ?, ?);"""
                    cursor.execute(sqlite_insert_query, data)
                except sqlite3.Error as error:
                    print("Не удалось вставить данные в таблицу sentences_markup")
                    print("Класс исключения: ", error.__class__)
                    print("Исключение", error.args)
                    print("Печать подробноcтей исключения SQLite: ")
                    exc_type, exc_value, exc_tb = sys.exc_info()
                    print(traceback.format_exception(exc_type, exc_value, exc_tb))
        sqlite_connection.commit()
        cursor.close()
    except sqlite3.Error as error:
        print("Ошибка при работе с SQLite", error)
    finally:
        if sqlite_connection:
            sqlite_connection.close()


def task_rule_gen(sent_text, sent_markup, sent_id, text_theme=''):
    if 2 < len(sent_text.split(' ')) < 31 and sent_text[0].isupper():  # отсекает слишком короткие / длинные
        # предложения и проверяет, что первая буква заглавная (то есть взято предложение с начала)
        verb, subj = '', ''
        obj, obl, iobj, xcomp, aux = [], [], [], [], []
        #exer_text, words_to_mod, answer = '', '', ''
        sent_markup = sent_markup[1:-1]
        sent_markup = sent_markup.split('); (')
        sent_markup = [_.split(', ', maxsplit=6) for _ in sent_markup]  # token.text, token.pos_, token.dep_,
        # token.head.text, token.idx, token.idx + len(token.text), token.children
        for word in sent_markup:  # [Формирование, NOUN, nsubj, является, [тематики], 0, 12]
            if word[0].isalpha and d.check(word[0]):  # исключает иностранные слова и слова с орфографическими ошибками
                if word[2] == "ROOT" and word[1] == 'VERB' and not verb:  # поиск сказуемого
                    verb = word
                    children_v = [_ for _ in sent_markup if _[0] in verb[6].split(', ')]  # список токенов, зависимых от глагола
                    # (I уровень)
                    for ch_v in children_v:
                        if d.check(ch_v[0]) and ch_v[0].isalpha():
                            if ch_v[2] in ["nsubj", "nsubj:pass"] and ch_v[1] in ['NOUN', 'PRON'] \
                                    and not subj and morph.parse(ch_v[0])[0].tag.case == 'nomn':  # поиск подлежащего
                                subj = ch_v
                            elif ch_v[2] == "obj":
                                obj.append(ch_v)
                            elif ch_v[2] == "obl":
                                obl.append(ch_v)
                            elif ch_v[2] == "xcomp":
                                xcomp.append(ch_v)
                            elif ch_v[2] == "iobj":
                                iobj.append(ch_v)
                if word[2] == "aux:pass":
                    aux.append(word)
        if not subj or not verb:
            return
        if morph.parse(subj[0])[0].tag.number != morph.parse(verb[0])[0].tag.number:
            return
        if morph.parse(verb[0])[0].tag.tense == 'past' and morph.parse(verb[0])[0].tag.number == 'sing':
            if morph.parse(subj[0])[0].tag.gender != morph.parse(verb[0])[0].tag.gender and \
                    morph.parse(subj[0])[0].tag.gender:
                return
        if subj[1] == "PRON":
            if morph.parse(subj[0])[0].tag.person != morph.parse(verb[0])[0].tag.person and \
                    morph.parse(verb[0])[0].tag.person:
                return
        if not obj and not obl and not iobj and not xcomp:
            return
        else:
            children_obj, children_obl, children_case, children_xcomp, aux_xcomp, nmod, case, fixed = [], [], [], [], [], [], [], []
            aux_text, obj_token, nmod_token, iobj_token, obl_token, case_token, fixed_token, aux_xcomp_token, xcomp_token = '', '', '', '', '', '', '', '', ''
            for _ in aux:  # всмогательный глагол для сказуемого
                if _[3] == verb:
                    aux_text = _[0]
            for _ in obj:
                children_obj.extend(_[6])
            children_obj = [_ for _ in sent_markup if _[0] in children_obj]
            for _ in children_obj:
                if _[2] == "nmod" and _[3] == subj[0] and d.check(_[0]):
                    nmod.append(_)
            for _ in obl:
                children_obl.extend(_[6])
            children_obl = [_ for _ in sent_markup if _[0] in children_obl]
            for _ in children_obl:
                if _[2] == "case" and d.check(_[0]):
                    case.append(_)
            for _ in case:
                children_case.extend(_[6])
                children_case = [_ for _ in sent_markup if _[0] in children_case]
                for _ in children_case:
                    if _[2] == "fixed" and d.check(_[0]):
                        fixed.append(_)
            for _ in xcomp:
                children_xcomp.extend(_[6])
                children_xcomp = [_ for _ in sent_markup if _[0] in children_xcomp]
                for _ in children_xcomp:
                    if [2] == "aux:pass" and d.check(_[0]):
                        aux_xcomp.append(_)
            if len(obj) == 1:
                obj_token = obj[0]
                nmod = [_ for _ in nmod if _[3] == obj_token[0]]
                if len(nmod) == 1:
                    nmod_token = nmod[0]
            if len(obl) == 1:
                obl_token = obl[0]
                case = [_ for _ in case if _[3] == obl_token[0]]
            if len(iobj) == 1:
                iobj_token = iobj[0]
            if len(xcomp) == 1:
                xcomp_token = xcomp[0]
                aux_xcomp_token = [_ for _ in aux_xcomp if _[3] == xcomp_token[0]]
                if aux_xcomp_token:
                    aux_xcomp_token = aux_xcomp_token[0]
            if len(case) == 1:
                case_token = case[0]
                fixed_token = [_ for _ in fixed if _[3] == case_token[0]]
                if fixed_token:
                    fixed_token = fixed_token[0]
            if not obj_token and not obl_token and not iobj_token and not xcomp_token:
                return
            else:
                tokens_to_replace = []
                exer_text = sent_text
                if obj_token:
                    tokens_to_replace = [aux_text, verb, obj_token, nmod_token]
                elif iobj_token:
                    tokens_to_replace = [aux_text, verb, iobj_token]
                elif xcomp_token:
                    tokens_to_replace = [aux_text, verb, xcomp_token]
                    tokens_to_replace.extend(aux_xcomp_token)
                elif obl_token:
                    tokens_to_replace = [aux_text, verb, obl_token, case_token, fixed_token]
                tokens_to_replace = [_ for _ in tokens_to_replace if _]
                tokens_to_replace.sort(key=lambda k: int(k[4]))
                for _ in tokens_to_replace:
                    exer_text = exer_text[:int(_[4])] + '_' * len(_[0]) + exer_text[int(_[5]):]
                exer_text = exer_text[:int(subj[4])] + '<b>' + subj[0] + '</b>' + exer_text[int(subj[5]):]
                words_to_mod = ' '.join([morph.parse(_[0])[0].normal_form.upper() for _ in tokens_to_replace])
                answer = ' '.join([_[0] for _ in tokens_to_replace])
                hint = ''
                tense = {'past': 'прошедшее', 'pres': 'настоящее', 'futr': 'будущее'}
                gender = {'masc': 'мужской', 'femn': 'женский', 'neut': 'средний'}
                number = {'sing': 'единственное', 'plur': 'множественное'}
                if morph.parse(verb[0])[0].tag.tense:
                    hint += 'время: ' + tense[morph.parse(verb[0])[0].tag.tense] + '\n'
                if morph.parse(verb[0])[0].tag.number:
                    hint += 'число: ' + number[morph.parse(verb[0])[0].tag.number] + '\n'
                if morph.parse(verb[0])[0].tag.gender:
                    hint += 'род: ' + gender[morph.parse(verb[0])[0].tag.gender]
                data = ('rule', exer_text, words_to_mod, answer, hint, int(sent_id), text_theme)
                return data


if __name__ == '__main__':
    get_rows()
    print('Done!')
