#!/usr/bin/python

# Populates missing Open Library Author Ids (P648) by inferring them from book information
# as follows:
#   - run sparql query to find authors lacking OL ids but with books with isbns
#   - lookup isbn in Open Library via their api
#   - if the book author's name matches add the OL id to author's Wikidata

import json
import re
import httplib2
import pywikibot

# unfortunately pywikibot's sparql functionality is rudimentary
import sparql

sparql_endpoint = 'https://query.wikidata.org/bigdata/namespace/wdq/sparql'
s=sparql.Service(sparql_endpoint,"utf-8", "GET")

query = """
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>

SELECT *
WHERE
{
   ?p wdt:P31 wd:Q571 . #type book
   ?p wdt:P212 ?isbn .  #that have an isbn-13
   ?p wdt:P50 ?author . #author
   optional {
    ?author wdt:P648 ?ol #open library author id
   }
   filter (!bound(?ol))  #filter those that have no OL author id
}
order by desc(?author)
"""

ol_prop = 'P648'

wikidata_site = pywikibot.Site("wikidata","wikidata")
repo = wikidata_site.data_repository()

# create an imported from reference claim to attribute the data from Open Library
imported_from_claim = pywikibot.Claim(repo, 'P143')
olr_item = pywikibot.ItemPage(repo, 'Q1201876') #open library
imported_from_claim.setTarget(olr_item)

def canon_name(name):
    # remove common punctuation, middle initial and spaces, lower case
    # swap last, first to first last
    name = re.sub(' [A-Z]\.? ',' ',name)
    if name.count(',') == 1:
        (a,b) = re.split(',',name)
        name = b + ' ' + a
    return re.sub('[\s\'\-\.\,]','',name.lower().strip())

def ol_isbn(isbn):
    h = httplib2.Http()
    openlibrary_url = 'https://openlibrary.org/api/books?bibkeys=ISBN:%s&jscmd=data&format=json'
    (resp_headers, resp)=h.request(openlibrary_url % isbn,'GET')
    ol = json.loads(resp)
    return ol

result = s.query(query)

#prev_author_url = False
for row in result.fetchone():
    (work,isbn,author_url,empty) = row
    isbn = isbn.value.replace('-','')
    author_url = author_url.value
    #print isbn
    match = re.match('http://www\.wikidata\.org/entity/(Q\d+)',author_url)
    #if( not (author_url == prev_author_url) and match and (len(isbn) == 13)):
    if( match and (len(isbn) == 13)):
        print 'author_url',author_url
        author_qid = match.group(1)
        author_item = pywikibot.ItemPage(repo, author_qid)
        author_item.get()
        labels = author_item.labels
        author_keys = labels.keys()
        if 'en' in author_keys:
            label = author_item.labels['en']
        else:
            label = author_item.labels[author_keys[0]]
        claims = author_item.claims.keys()

        # check that there is a label to match against
        # that there is not already an OL id
        # and that the instance of is human (Q5)
        if label and (not ol_prop in claims) and 'P31' in claims and author_item.claims['P31'][0].target.title() == 'Q5':
            ol = ol_isbn(isbn)
            if len(ol.keys()) > 0:
                print 'label',label
                k = ol.keys()[0]
                if 'authors' in ol[k].keys():
                    for author in ol[k]['authors']:
                        print author['name']
                        if canon_name(label) == canon_name(author['name']):
                            ol_match = re.match('https://openlibrary.org/authors/(OL\d+A)/',author['url'])
                            if ol_match:
                                ol_id = ol_match.group(1)
                                print 'matched', ol_id
                                claim = pywikibot.Claim(repo, ol_prop)
                                claim.setTarget(ol_id)
                                author_item.addClaim(claim)
                                claim.addSource(imported_from_claim)
                                break
    #prev_author_url = author_url
