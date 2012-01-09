from couchdbkit import Server, Document, StringProperty, DateTimeProperty
import simplejson
import datetime
import logging
import urllib
import re

APIKEY = 'XXX' #google api key
COUCHDB_URI = "http://user:password@server:5984/"
TRANSLATE_URI= "https://www.googleapis.com/language/translate/v2"
COUCHDB="dictionaries"

#todo change debug level through console
LOG_FILE = 'translate.log'
LOG_LEVEL = logging.INFO


class UserRecord(Document):
   user_name = StringProperty()
   creation_time = DateTimeProperty()
   
   def contains(self, key):
      return self.__contains__(key)

class DictionaryRecord(Document):
   source = StringProperty()
   target = StringProperty()
   query = StringProperty()
   word_source = StringProperty()
   date_written = DateTimeProperty()

class Backend:
   def __init__(self):
      self.bot_log = logging.getLogger("Bot Logger")
      if not self.bot_log.handlers:
          hdlr= logging.FileHandler(LOG_FILE)
          formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
          hdlr.setFormatter(formatter)
          self.bot_log.addHandler(hdlr)
      self.bot_log.setLevel(LOG_LEVEL)                             
      self.bot_log.info("bot loaded.")
      
   def version(self, mess, args):
      VERSION = "0.0.1b"
      return VERSION
   
   def translate(self, mess, args):
      params = {}
   
      #todo: regex not handling all assignment cases correctly
      if args.count("="):
         regex = re.compile("(?P<key>\w*?)=(?P<value>\w*?)\s|$")
         last_value = ""
         for (k, v) in regex.findall(args):
            if k and v:
               params[k.lower()] = v            
               last_value = v
            
         #urls can be crazy and all those '=' signs can muck things up         
         if len(args.split("word_source=")) > 1:
            params['word_source'], args = self.get_word_source(args)
        
         if len(args.split("="+last_value+" ")) > 1:
            params['query'] = args.split("="+last_value+" ")[1].strip()
        
      else:
        params['query'] = args.strip()
      
      try:
        self.bot_log.debug("connecting to server: %s" % COUCHDB_URI)
        server = Server(COUCHDB_URI)
      except:
        self.bot_log.error("could not connect to database %s" % COUCHDB_URI)
        return "hi"
        #return "could not connect to database."
      try:
        db = server.get_or_create_db(COUCHDB)   
      except:
        self.bot_log.error("could not create or access database: %s" % COUCHDB)      
        return "could not create or access dictionary database."
        
      UserRecord.set_db(db)
      user = str(mess.getFrom())
      
      result = db.view("user_record/last_used", key=user)
      self.bot_log.info("getting record: user_record/last_used: %s" % user)
      if result.count() == 0:
        user_record = UserRecord(
          user_name = user,
          creation_time = datetime.datetime.utcnow()
        )
      
      if result.count() > 1:     
        self.bot_log.error("ERROR: Multiple User Records found.")
        return "ERROR: Multiple User Records found."
        
      else:      
        record = result.one()
        user_record = UserRecord.get( record['id'])
        
        #dump parameters not in quesy into user_record
        missing_params =  set(['source', 'target', 'word_source']).difference(set(params))
        for each in missing_params:
         if record['value'].has_key('last_'+each): 
            user_record['last_'+each] = record['value']['last_'+each]
                 
      #dump parameters into user_record
      for each in params:      
        user_record['last_'+each] = params[each]

      #Logic check (More to come?)
      if len(missing_params) == 3 and not params.has_key('query'):
         return "Error: No query or setting present:\n" + \
                "Available setting are:\n" + \
                "source\n" + "target\n" + "word_source\n"
         
      if user_record['last_source'] == user_record['last_target']:
         return "Error: source language and target language are the same."      

             
      #don't save query & refresh
      if user_record.contains('last_query'): del user_record['last_query'] 
      if user_record.contains('last_refresh'): del user_record['last_refresh']
          
      # if not query updated
      if params: user_record.save() 
      if not params.has_key('query'):
       self.bot_log.info("User Record Updated")
       return "User Record Updated"
      
      DictionaryRecord.set_db(db)
      dict_record = db.view("dictionary_record/translate", 
                      key=[params['query'],
                      user_record['last_source'], 
                      user_record['last_target'] ])
   
      #we should be building pipeline
      #this will change when we split into runners and add other ones but for the moment
      #any one key won't have more than two records
      #if refresh == both
      #  write log entries and fire translate functions
      #if refresh == shallow
      #  write log entry and fire translate shallow
      #if refresh == full
      #  write log entry and fire translate full
      #else
      #  for each record: display  
      response_message = ""
      if dict_record.count():        
        for each in dict_record:
          if each['value'][0]:
            if params.has_key('refresh') and (params['refresh'] == 'shallow' or \
                                      params['refresh'] == 'both'):
               self.bot_log.info("refreshing shallow record: %s" % params['query'])
               response_message += self.translate_shallow(mess, params, user_record, each['id'])                                              
            else:
               self.bot_log.info("retrieved shallow record: %s" % params['query'])
               response_message += "simple: " + each['value'][1] + "\n"                
          else:
            if params.has_key('refresh') and (params['refresh'] == 'full'  or \
                                      params['refresh'] == 'both'): 
               self.bot_log.info("refreshing full record: %s" % params['query'])
               response_message += self.translate_full(mess, params, user_record, each['id'])
            else:                                  
               full_lookup = [];
               self.bot_log.info("retrieved full record: %s" % params['query'])
               for part_of_speech in each['value'][1].keys():                
                 full_lookup.append(part_of_speech + ":")
                 for word in each['value'][1][part_of_speech]:
                   full_lookup.append(word)
                 full_lookup.append("")
        
               response_message += "\n".join(full_lookup)
          
          #just turning off for now
          #todo: giant hack! and will refresh twice if full record is present 
          #if params.has_key('refresh') and (params['refresh'] == 'full'  or  params['refresh'] == 'both'):
          #     self.bot_log.info("refreshing full record: %s" % params['query'])
          #     response_message += self.translate_full(mess, params, user_record, each['id'])
      else:
        response_message += self.translate_shallow(mess, params, user_record)
        response_message += self.translate_full(mess, params, user_record)
      
      return response_message
   
   def translate_shallow(self, mess, params, user_record, doc_id=False):
        search_params = {       
         'source' : user_record['last_source'].lower(), 
         'target' : user_record['last_target'].lower(), 
         'q' : params['query'].encode('UTF-8'),   
         'key' : APIKEY,           
        }
        
        URL = TRANSLATE_URI + '?' + urllib.urlencode(search_params)
        self.bot_log.debug("used shallow search URL: %s" % URL)
        result = simplejson.load(urllib.urlopen(URL))
        self.bot_log.debug("shallow json return: %s" % result)
        translatedText = self.parse_json(result)                
        if translatedText.lower() == params['query'].lower():
         self.bot_log.info("translation found")
         return "No simple translation found.\n"
                 
        if doc_id:
          shallow_drecord = DictionaryRecord.get(doc_id)
          shallow_drecord['source'] = user_record['last_source'] 
          shallow_drecord['target'] = user_record['last_target'] 
          shallow_drecord['query'] = params['query'] 
          shallow_drecord['translated'] = translatedText
          shallow_drecord['shallow'] = True
          shallow_drecord['date_written'] = datetime.datetime.utcnow()
          if user_record.contains('last_word_source'): shallow_drecord['word_source'] = user_record['last_word_source']
          shallow_drecord.save()
          
        else:
          shallow_drecord = DictionaryRecord(
            source = user_record['last_source'], 
            target = user_record['last_target'], 
            query = params['query'],          
            translated = translatedText,
            shallow = True,
            date_written = datetime.datetime.utcnow()
          )
          if user_record.contains('last_word_source'):  shallow_drecord['word_source'] = user_record['last_word_source']
          shallow_drecord.save()
        
        self.bot_log.info("shallow translation record saved.") 
        return translatedText + "\n"
   
        
   def translate_full(self, mess, params, user_record, doc_id=False):
      search_params = {       
         'sl' : user_record['last_source'].lower(), 
         'tl' : user_record['last_target'].lower(), 
         'q' : params['query'].encode('UTF-8'),             
      }
      URL="http://www.google.com/dictionary/json?callback=dict_api.callbacks.id100&" + urllib.urlencode(search_params)   
      PROXY={'http': 'http://localhost:8118'}
      fp = urllib.urlopen(URL,proxies=PROXY)
      dirty = fp.read()
      self.bot_log.debug("used full search URL: %s" % URL)
      self.bot_log.debug("full json return: %s" % dirty)
      #we might have to watch out for more API failures or male formed requests
      if not dirty.split(",")[-2] == '200':
       self.bot_log.error("url request: %s didn't return successfully" % URL)
       self.bot_log.error("return: %s" % dirty)     
       return ""
      clean = self.clean_json(dirty)
      json = simplejson.loads(clean)
      
      word_list = {}
      printable = []
      try: 
        for each in json['primaries'][0]['entries']: 
          word_list[each['labels'][0]['text']] = []
          printable.append(each['labels'][0]['text'] +":")
          for term in each['entries']:
            word_list[each['labels'][0]['text']].append(term['terms'][0]['text'])
            printable.append(term['terms'][0]['text'])
      except KeyError, e:
       self.bot_log.error("key %s not found" % e)
      
      if not word_list:
        return "No complex translation found.\n"
          
      if doc_id:
        full_drecord = DictionaryRecord.get(doc_id)
        full_drecord['source'] = user_record['last_source'] 
        full_drecord['target'] = user_record['last_target']
        full_drecord['query'] = params['query']
        full_drecord['translated'] = word_list
        full_drecord['shallow'] = False
        full_drecord['date_written'] = datetime.datetime.utcnow()
        if user_record.contains('last_word_source'):full_drecord['word_source'] = user_record['last_word_source']
        
        full_drecord.save()         
      else:
        full_drecord = DictionaryRecord(
          source = user_record['last_source'], 
          target = user_record['last_target'], 
          query = params['query'],
          word_source = user_record['last_word_source'],
          translated = word_list,
          shallow = False,
          date_written = datetime.datetime.utcnow()
        )
        if user_record.contains('last_word_source'):full_drecord['word_source'] = user_record['last_word_source']
        full_drecord.save()     
       
      self.bot_log.info("full translation record saved.")         
      return "\n".join(printable) + "\n"


   #helper functions
   
   def get_word_source(self, args):
      #kinda hacking but we're doing it for now
      if args.split("word_source")[1].find(" ") == -1:
	     word_source = args.split("word_source=")[1][0:]
	     clean_args = args.replace("word_source=" + word_source,"")
      else:
	     word_source = (args.split("word_source=")[1][0:args.split("word_source")[1].find(" ")]).strip()
	     clean_args = args.replace("word_source=" + args.split("word_source=")[1][0:args.split("word_source")[1].find(" ")],"")
      return (word_source, clean_args)
   
   def parse_json(self, json):
      #todo more pythonicly
      import pdb; pdb.set_trace()
      if json['error']:
         return "Error: %s (%s)" % (json['error']['message'], json['error']['code'])
      try:
         translatedText = json['data']['translations'][0]['translatedText']
      except:
         translatedText = json['data']['translations'][0]['translated_text']
      finally:
         return translatedText
     

   def clean_json(self, payload):
      for single_tic in ('\\x27', '\\x26#39;'):
         payload = payload.replace(single_tic, "'")      
      for erase in ("dict_api.callbacks.id100(",",200,null)"):
         payload = payload.replace(erase, "")
      return payload
   
   
   
#Todo
#html front_end
#http://janmonschke.github.com/backbone-couchdb/app.html
#http://documentcloud.github.com/backbone/docs/todos.html

#auto detect if debugging
#move to 4 spaces
#short cuts t(l)=target, s(l)=source, w(s)=word_source

#add offline mode
#urllib2.urlopen('http://api.wordreference.com/19863/json/enit/keys').read()
#add deletion interface 
#turn off daemon
#change LOG_LEVEL via XMPP
#switch to runners using 0mq
#Import old words from text files
#unify error structure
#add language look table
#add authentication system
#add sessionizing
#add firefox plugin
#change to plugin system for look ups
#add sync option
#conjuction plugin using word reference
#add full text looks using lucene
