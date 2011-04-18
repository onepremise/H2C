# -*- coding: utf-8 -*-

# Copyright (c) 2010, Webreactor - Marcin Lulek <info@webreactor.eu>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#    * Neither the name of the <organization> nor the
#      names of its contributors may be used to endorse or promote products
#      derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
import htmlentitydefs
from htmlentitydefs import name2codepoint
import re
import string
import chardet

try:
  from lxml import etree
except ImportError:
  try:
    # Python 2.5
    import xml.etree.cElementTree as etree
  except ImportError:
    try:
      # Python 2.5
      import xml.etree.ElementTree as etree
    except ImportError:
      try:
        # normal cElementTree install
        import cElementTree as etree
      except ImportError:
        try:
          # normal ElementTree install
          import elementtree.ElementTree as etree
        except ImportError:
          print("Failed to import ElementTree from any known place")

class EchoTarget:
    
    def __init__(self):
        self.final_output = []
        self.block = False
        self.ol_ident = 0
        self.ul_ident = 0
        self.list_types = []
        self.haystack = []
        self.is_dv_toc = 0

        self.th_parse = 0
        self.td_parse = 0

    def __processAttrib(self, attrib):
        if 'style' in attrib:
            style_value = '{%s}' % attrib['style'][:-1]
        else:
            style_value = ''

        if 'class' in attrib:
            class_value = '(%s)' % attrib['class']
        else:
            class_value = ''

        if 'id' in attrib:
            id_value = '(#%s)' % attrib['id']
        else:
            id_value = ''

        if 'lang' in attrib:
            lang_value = '[%s]' % attrib['lang']
        else:
            lang_value = ''

        return ( style_value, class_value, id_value, lang_value )
    
    def start(self, tag, attrib):    
        newline = ''
        dot = ''
        new_tag = ''

        style_value = '' 
        class_value = '' 
        id_value = '' 
        lang_value = ''

        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            new_tag = tag
            dot = '. '
	elif tag == 'div':
            if 'id' in attrib and 'content' == attrib['id']:
                new_tag=''
                dot = ''
                style_value = '{TOC}\n\n'
                self.is_dv_toc = 1
		newline = '\n'
#            else:
#                new_tag = '{div'
#
#                firstrun=1
#                
#                for item, value in attrib.items():
#                    if firstrun==1:
#                        new_tag = new_tag+':'
#                    elif firstrun==0:
#                        new_tag = new_tag+'|'
#
#                    new_tag = new_tag+item+'='+value+''
#
#                    firstrun=0
#
#                new_tag = new_tag + '}'
#
#                dot = ''
        elif tag == 'p':
#            ( style_value, class_value, id_value, lang_value ) = self.__processAttrib(attrib)
#            if style_value or lang_value:
#                new_tag = 'p'
#                dot = '. '
#            else: 
                new_tag = ''
                dot = ''
        elif tag == 'blockquote':
            new_tag = 'bq'
            dot = '. '
            ( style_value, class_value, id_value, lang_value ) = self.__processAttrib(attrib)
        elif tag in ('b', 'strong'):
            new_tag = '*'
            newline = ''
        elif tag in ('em', 'i'):
            new_tag = '_'
            newline = ''
        elif tag == 'cite':
            new_tag = '??'
            newline = ''
        elif tag == 'del':
            new_tag = '-'
            newline = ''
        elif tag == 'ins':
            new_tag = '+'
            newline = ''
        elif tag == 'sup':
            new_tag = '^'
            newline = ''
        elif tag == 'sub':
            new_tag = '~'
            newline = ''
        elif tag == 'span':
            new_tag = ''
            newline = ''
        elif tag == 'a':
            self.block = True
            if 'title' in attrib:
                self.a_part = {'title':attrib.get('title'),
                               'href':attrib.get('href', '')}
            else:
                self.a_part = {'title':None, 'href':attrib.get('href', '')}
            new_tag = ''    
            newline = ''
            
        elif tag == 'img':
            new_tag = ' !%s' % attrib.get('src')
            newline = ''
            
        elif tag in ('ul', 'ol'):
            new_tag = ''    
            newline = ''
            self.list_types.append(tag)
            if tag == 'ul':
                self.ul_ident += 1
            else:
                self.ol_ident += 1
            
        elif tag == 'li':
            indent = self.ul_ident + self.ol_ident
            if self.list_types[-1] == 'ul':
                new_tag = '*' * indent + ' '
                newline = '\n'
            else:
                new_tag = '#' * indent + ' '    
                newline = '\n'
        elif tag == 'th':
            self.th_parse = 1
            new_tag = '|| '
            newline = ''
        elif tag == 'tr':
            new_tag = ''
            newline = ''
        elif tag == 'td':
            self.td_parse = 1
            new_tag = '| '
            newline = ''
        elif tag == 'font':
            new_tag = ''
            newline = ''

        if tag not in ('ul', 'ol'):
            textile = '%(newline)s%(tag)s%(id)s%(class)s%(style)s%(lang)s%(dot)s' % \
                                 {
                                  'newline':newline,
                                  'tag':new_tag,
                                  'id':id_value,
                                  'class':class_value,
                                  'style':style_value,
                                  'lang':lang_value,
                                  'dot':dot
                                  }
            if not self.block:
                self.final_output.append(textile)
            else:
                self.haystack.append(textile)
        
    def end(self, tag):
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p'):
            self.final_output.append('\n')
	elif tag == 'title':
	    self.final_output.append('\n')
        elif tag == 'div':
            if self.is_dv_toc:
                 self.final_output.append('\n')
                 self.is_dv_toc = 0
#            else:
#                 self.final_output.append('{div}\n')
        elif tag in ('b', 'strong'):
            self.final_output.append('*')
        elif tag in ('em', 'i'):
            self.final_output.append('_')
        elif tag == 'cite':
            self.final_output.append('??')
        elif tag == 'del':
            self.final_output.append('-')
        elif tag == 'ins':
            self.final_output.append('+')
        elif tag == 'sup':
            self.final_output.append('^')
        elif tag == 'sub':
            self.final_output.append('~')
        elif tag == 'span':
            self.final_output.append('')
        elif tag == 'font':
            self.final_output.append('')
        elif tag =='br':
            self.final_output.append('\n')
        elif tag == 'a':
            retrieved_value=''.join(self.haystack)
            if self.a_part['title']:
                textilized = '[%s (%s)|%s]' % (
                                                 retrieved_value,
                                                 self.a_part.get('title'),
                                                 self.a_part.get('href'),
                                                 )
                self.haystack = []
            elif retrieved_value:
                textilized = '[%s'%retrieved_value
		href=self.a_part['href']

                if href.find("://")>-1:
                    textilized += '|%s]' % self.a_part.get('href')
		elif href:
                    textilized += ':%s]' % self.a_part.get('href')
                else:
                    textilized += ']'

                self.haystack = []  
            elif self.a_part['href']:
                textilized = '[%s]' % self.a_part.get('href')
                self.haystack = []  
            else:
                textilized = ''.join(self.haystack)
                self.haystack = []

            self.final_output.append(textilized)
            self.block = False
        elif tag == 'img':
            self.final_output.append('!')
        elif tag == 'th':
            self.final_output.append(' ')
        elif tag == 'tr':
            if self.th_parse:
                self.final_output.append(' ||')
            elif self.td_parse:
                self.final_output.append(' |')

            self.final_output.append('\n')

            self.th_parse=0
            self.td_parse=0
        elif tag == 'td':
            self.final_output.append(' ')
        elif tag == 'ul':
            self.ul_ident -= 1
            self.list_types.pop()
            if len(self.list_types) == 0:
                self.final_output.append('\n')
        elif tag == 'ol':
            self.ol_ident -= 1
            self.list_types.pop()
            if len(self.list_types) == 0:
                self.final_output.append('\n')

    def __descape_entity(self, m, defs=htmlentitydefs.entitydefs):
        # callback: translate one entity to its ISO Latin value
        try:
            return defs[m.group(1)]
        except KeyError:
            return m.group(0) # use as is

    def __descape(self, string):
        pattern = re.compile("&(\w+?);")
        return pattern.sub(self.__descape_entity, string)

    def __htmlentitydecode(self, s):
        return re.sub('&(%s);' % '|'.join(name2codepoint), 
                lambda m: unichr(name2codepoint[m.group(1)]), s)

    def data(self, data):
        node_data = data.replace(u'\xa0',' ')
	node_data = node_data.replace('[', '\[')
        node_data = node_data.replace(']', '\]')

        if not self.block:
            self.final_output.append(node_data)
        else:
            self.haystack.append(node_data)

    def comment(self, text):
        pass

    def close(self):
        return "closed!"

 
def html2textile(html):
    #1st pass
    #clean the whitespace and convert html to xhtml
    encoding = chardet.detect(html)['encoding']

    if encoding != 'utf-8':
        html = html.decode(encoding, 'replace').encode('utf-8')

    parser = etree.HTMLParser(encoding = 'utf-8')
    tree = etree.fromstring(html, parser)
    xhtml = etree.tostring(tree, method="xml")
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.XML(xhtml, parser)
    cleaned_html = etree.tostring(root)
    #2nd pass build textile
    target = EchoTarget()
    parser = etree.XMLParser(target=target)
    root = etree.fromstring(cleaned_html, parser)
    textilized_text = ''.join(target.final_output).lstrip().rstrip()
    return textilized_text
