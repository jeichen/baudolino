#!/usr/bin/python

#suppress version warning when using python2.6
import warnings
warnings.simplefilter("ignore",DeprecationWarning)

from jabberbot import JabberBot, botcmd
import datetime

from backend import Backend

class TranslateBot(JabberBot):
   """My Translator Bot"""
   
   def __init__(self, username, password, res=None, debug=False):
      self.backend = Backend()
      JabberBot.__init__(self, username, password, res, debug)
   
   @botcmd
   def bot_time(self, mess, args):
      """Displays current server time"""
      return str(datetime.datetime.now())
   
   @botcmd
   def version(self, mess, args):
      """print current version of module"""
      return self.backend.version(mess, args)
   	  
   @botcmd(hidden=True)
   def reload(self, mess, args):
      """DEBUG: reload module"""
      import backend
      reload(backend)
      self.backend = backend.Backend()
      return "module reloaded."

   @botcmd
   def translate(self, mess, args):      
      """translate: TODO add help"""
      return self.backend.translate(mess, args)
   
   @botcmd(hidden=True, default=True)
   def trans(self, mess, args):
      return self.backend.translate(mess, args) 
        
def main():   
   #jabber client login
   username = 'username@server'
   password = 'password'
   bot = TranslateBot(username,password)
   
   while 1:
      try:
         bot.serve_forever()
         break
      except AttributeError, e:
         print "Error %s" % e
         print "retrying..."

if __name__ == "__main__":   
      main()
