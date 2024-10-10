import spacy

nlp = spacy.load("ja_ginza")

def get_nlu_result(text):
    """テキストを受け取ってspaCyの解析結果をdictで返す返す"""
    
    doc = nlp(text)
    token_results = []
    for sent in doc.sents:
        for token in sent:
            reading = token.morph.get("Reading", "")
            inflection = token.morph.get("Inflection", "")
            print(
                # token.i,
                token.orth_,
                token.lemma_,
                token.norm_,
                reading,
                token.pos_,
                inflection,
                token.tag_,
                token.dep_,
                token.head.i,
            )
            
            token_results.append(
                {
                    "token": token.orth_,
                    "lemma": token.lemma_,
                    "norm": token.norm_,
                    "reading": reading,
                    "pos": token.pos_,
                    "inflection": inflection,
                    "tag": token.tag_,
                    "dep": token.dep_,
                    "head": token.head.i,
                }
            )

    entity_results = []
    # 文中のエンティティを表示
    for ent in doc.ents:
        print(f"エンティティ: {ent.text}, ラベル: {ent.label_}")
        for token in ent:
            print(token.text, token.tag_)
            entity_results.append(
                {
                    "entity": ent.text,
                    "label": ent.label_,
                    "token": token.text,
                    "tag": token.tag_,
                }
            )
    return token_results, entity_results
