#!/usr/bin/python
# -*- coding: utf-8 -*-

#    h2c.py - converts html to textile; uploads content and attacments.
#    Copyright (C) 2011  Jason Huntley
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
import sys
import re
import string
import os
from html2textile import html2textile
import shutil
import xmlrpclib
from xmlrpclib import Server
from collections import deque

class H2C:
    def __init__(self):
        self.server=''
        self.login=''
        self.passwd=''

        self.space='default'

        self.source='source'
        self.destination='converted'
        self.attachements='attachments'

        self.linksToReplace=[]
        self.imagesToReplace=[]

    def __testConnection(self):
        print '\nTesting Connection...'

        try:
            server = xmlrpclib.ServerProxy(self.server)
        except Exception, e:
            print "\nError: Invalid URL!"
            print unicode(str(e))
            print '\n\n'
            return False

        try:
            s = Server(self.server)
            token = s.confluence1.login(self.login, self.passwd)
            s.confluence1.logout(token)
        except Exception, e:
            print '\n'
            print unicode(str(e))
            print "\n"
            return False

        print 'Successful Testing Connection!'

        return True

    def __normalizeString(self, value, useTitle):
        value=value.replace('-',' ')

        if useTitle:
            value=value.title()

        value=value.replace('(', '')
        value=value.replace(')', '')
        value=value.replace(' ', '')

        return value

    def __matchNormalizedString(self, path, useTitle=0):
        components = path.split(os.sep)
        newpath=''

        for c in components:
            if c != self.destination and c != self.attachements:
                c=self.__normalizeString(c, not c[0].isupper())
            newpath=os.path.join(newpath,c)

        return newpath

    def __convertContents(self, dir, recreateFullPath):
        for root, subFolders, files in os.walk(dir):
            for folder in subFolders:
               # folder=self.__normalizeString(folder)
                if recreateFullPath:
                    d=os.path.join(root,folder)
                else:
                    d=''

                newd=os.path.join(self.destination,d)

                newd=self.__matchNormalizedString(newd, 1)

                if not os.path.exists(newd):
                    print 'Createing directory=%s' % newd
                    os.makedirs(newd)

            for file in files:
                f=os.path.join(root,file)
                basename, extension = os.path.splitext(f)

                if not recreateFullPath:
                    basename=os.path.basename(basename)

                basename=os.path.join(self.destination, basename)

                if (extension == '.html'):
                    self.__convertFile(f,basename)
                    print '\n'
                else:
                    
                    if recreateFullPath:
                        newf=basename+extension
                        newf=self.__matchNormalizedString(newf, 1)
                        shutil.copyfile(f, newf)    
                    else:
                        basename=os.path.basename(file)
                        attachment=os.path.join(self.attachements,basename)
                        attachment=self.__matchNormalizedString(attachment, 1)
                        shutil.copyfile(f, attachment)

                    #if (extension in ['.jpg', 'gif']):
                    #    self.imagesToReplace .append(f)

    def __globalImageReplace(self, image):
        basename=os.path.basename(image)
        for dname, dirs, files in os.walk(self.destination):
            if dname.rfind('attachments')<0:
                for fname in files:
                    fpath = os.path.join(dname, fname)
                    s=''

                    with open(fpath) as f:
                            s = f.read()

                    if s.find(basename)>-1:
                        print 'UPDATE IMAGE: %s FILE: %s' % (basename, fname)
                        p = re.compile('\! *%s' % basename)

                        s=p.sub('!'+basename, s)
                        with open(fpath, "w") as f:
                            f.write(s)

    def  __getHTMLTitle(self, html):
        testValue=re.compile('<title>.*</title>', re.IGNORECASE)
        m = testValue.search(html)
        title=string.replace(m.group(), ' ', '')
        title=string.replace(title, '<title>', '')
        title=string.replace(title, '</title>', '')
        return title

    def __convertFile(self, f, fdestination):
        htmlfile=open(f)
        htmlfile.seek(0)
        html=htmlfile.read()
        htmlfile.close()

        title=self.__getHTMLTitle(html)

        fdestination=os.path.dirname(fdestination)
        fdestination=os.path.join(fdestination, title)
        fdestination=self.__matchNormalizedString(fdestination, 1)

        print 'Converting HTML %s, Content size: %s' % (fdestination, len(html))

        html=self.__cleanLinks(html)

        result=html2textile(html)
        
        fdestination=self.__getUniqueFileName(fdestination)

        newFile=open(fdestination, 'w')
        newFile.write(result.encode('UTF-8'))
        newFile.close()

        self.__flagLink(f, fdestination)
        
    def __getUniqueFileName(self, fdestination):
        newfilename=fdestination
        i=1

        while os.path.exists(newfilename):
            newfilename=fdestination+str(i)
            i+=1
        if os.path.basename(fdestination).lower()=='home':
            newfilename=fdestination+'1'
            newfilename=self.__getUniqueFileName(newfilename)

        return newfilename

    def __flagLink(self, f, fdestination):
        updatedSource=f.replace(self.source, '')
        updatedDest=fdestination.replace(self.destination, '')
        updatedDest=os.path.basename(updatedDest)

        updatedSource=self.__stripHtmlExt(updatedSource, updatedSource)

        entry=updatedSource, updatedDest

        self.linksToReplace.append(entry)
        
        
    def __processLinks(self):
        print 'PROCESSING LINKS...'
        for (s, d) in self.linksToReplace:
            self.__globalReplace(s,d)

    def __processImages(self):
        print 'PROCESSING IMAGES...'
        for f in self.imagesToReplace:
            self.__globalImageReplace(f)

    def __globalReplace(self, oldLink, newLink):
        for dname, dirs, files in os.walk(self.destination):
            for fname in files:
                oldLink=oldLink.strip('/')
                newLink=newLink.strip('/')

                self.__replaceLink(dname, fname, oldLink, newLink)

    def __replaceLink(self, dname, fname, oldLink, newLink):
        fpath = os.path.join(dname, fname)
        updated = 0
        with open(fpath) as f:
                    s = f.read()

        testValue=re.compile('\[ *.+? *\: *(.+?) *\]')
        m = testValue.finditer(s) 

        for item in m:
            originalValue=item.group(0)

            if len(originalValue)<=5 or originalValue.count(':')>1:
                continue

            value=item.group(1)

            if len(value)<=5:
                continue

            if not all(c in string.printable for c in originalValue):
                continue

            value=value.replace('..', '').strip('/')

            if oldLink.find(value)>-1 and value.find('http')<0 and value.find('/')>-1:
                newformattedLink='[%s:%s]' % (self.space, newLink)

                print '\nUPDATEING LINK-p: File=%s; Val=%s' % (fname, value)
                print 'DETAILS ORIGINAL: %s, SPECIFIC: %s' % (originalValue, value)
                print 'NEW FULL LINK %s' % newformattedLink

                s=s.replace(originalValue, newformattedLink)
                updated = 1

        if s.find(oldLink)>-1:
            print 'UPDATE LINK-f: %s:%s -> %s' % (fname, oldLink, newLink)

            p = re.compile('\| *%s' % oldLink)
            s=p.sub('|'+newLink, s)

            updated = 1

        if updated == 1:
            with open(fpath, "w") as f:
                f.write(s)        

    def __cleanLinks(self, html):
        #testValue=re.compile('href[^=]*=.+?\.html', re.IGNORECASE|re.MULTILINE)
        testValue=re.compile('href[^=]*=.+?"', re.IGNORECASE|re.MULTILINE)
        m = testValue.findall(html) 
        if len(m)>0:
            for item in m:
                if not 'http:' in item:
                    html=self.__stripHtmlExt(item, html)
                elif 'localhost' in item:
                    html=self.__stripHtmlExt(item, html)
                    html=self.__stripLocalhost(item, html)

        return html

    def __stripHtmlExt(self, url, content):
        newVal=string.replace(url, '.html', '')
        p = re.compile(url)
        content=p.sub(newVal, content)
        return content

    def __stripLocalhost(self, url, content):
        p = re.compile('http:\/\/localhost.+?\/')
        content=p.sub('', content)
        return content

    def setServer(self, s):
        self.server=s
        self.server=self.server+'/rpc/xmlrpc'

    def setUser(self, u):
        self.login=u

    def setPass(self, p):
        self.passwd=p

    def setSpace(self, s):
        self.space=s

    def setSource(self, s):
        self.source=s

    def setDestination(self, d):
        self.destination=d

    def process(self):
	if not self.__testConnection():
            return False

        if not os.path.exists(self.destination):
            print 'Creating destination: %s' % self.destination
            os.makedirs(self.destination)

        self.attachements=os.path.join(self.destination, self.attachements)
            
        if not os.path.exists(self.attachements):
            print 'Creating destination: %s' % self.attachements
            os.makedirs(self.attachements)

        self.__convertContents(self.source, 1)
        self.__processLinks()
        self.__processImages()

        return True

    def loadPages(self):
        s = Server(self.server)
        token = s.confluence1.login(self.login, self.passwd)

        destList=os.walk(self.destination)
        for root, subFolders, files in os.walk(self.destination):
            for folder in subFolders:
                dpath=os.path.join(root,folder).replace('(','').replace(')','')
                self.__createDir(s, token, dpath)
            for fle in files:
                fullrelpath = os.path.join(root, fle).replace('(','').replace(')','')
                basename, ext = os.path.splitext(fullrelpath)

                if ext == '':
                    print('loading page: %s' % fullrelpath)
                    self.__loadPage(s, token, fullrelpath)
                else:
                    print('loading attachment: %s:' % fullrelpath)
                    self.__loadAttachment(s, token, fullrelpath)
		
		print '\n'

    def __getPageID(self, server, token, parent, parentID=None):
        components = deque(parent.split(os.sep))

        c=components.popleft()
        try:
            if parentID == None:
                page = server.confluence1.getPage(token, self.space, c)
            else:
                page = server.confluence1.getPage(token, parentID)

            pagesummaries = server.confluence1.getChildren(token, page['id'])

            if len(components)>0 and pagesummaries is not None:
                if len(pagesummaries)>0:
                    for ps in pagesummaries:
                        if ps['title'] == components[0]:
                            nextpath=os.path.join(*components)
                            return self.__getPageID(server,token,nextpath,ps['id'])
            elif len(components) == 0:
                return page['id']
        except Exception, e:
            print('ERROR: Parent parse failed: %s, %s' % (self.space,c))
            print('EXCEPTION %s' % unicode(str(e)))
            return None
        
        return None

    def __renameOldDuplicates(self, server, token, pagename):
        count=1

        try:
            originalpage = server.confluence1.getPage(token, self.space, pagename)
            page=originalpage
        except:
            page=None

        while page is not None:
            nextpagename=pagename+str(count)

            try:
                page = server.confluence1.getPage(token, self.space, nextpagename)
            except:
                page = None

            if page is None:
                print 'Rename old duplicate %s' % originalpage['title']
                originalpage['title']=nextpagename
                server.confluence1.storePage(token, originalpage)

            count+=1

    def __createDir(self, server, token, dpath):
        dpath=dpath.replace(self.destination, '').strip('/')
        basename=os.path.basename(dpath)
        parent=os.path.dirname(dpath)
        parentID = None

        print('Checking path: "%s"' % dpath)
        if len(parent)>0:
            parentID=self.__getPageID(server, token, parent)
            print 'Parent ID=%s' % parentID

        newDirID=self.__getPageID(server, token, dpath)

        if newDirID is not None:
            print 'Directory exist already: %s; skipping...' % basename
            return

        self.__renameOldDuplicates(server, token, basename)

        newpagedata = {"title":basename, "content":" ","space":self.space}

        if parentID is not None:
            print 'Assigning parentID: %s' % parentID
            newpagedata['parentId']=parentID
            print newpagedata

        try:
            newpage = server.confluence1.storePage(token, newpagedata)
            print 'Successfully created: %s' % newpage['title']
        except Exception, e:
            print 'ERROR: Failed to create %s' % basename
            print('EXCEPTION: %s\n' % unicode(str(e)))

                
    def __loadPage(self, server, token, fpath):
        f=open(fpath)
        f.seek(0)
        content=f.read()
        f.close()

        relpath=fpath.replace(self.destination, '').strip('/')

        basename=os.path.basename(relpath)
        parent=os.path.dirname(relpath).strip('/')

        baseparent=os.path.basename(parent)
        print 'Checking to see if base(%s)==baseparent(%s)...' % (basename, baseparent)
        if basename.lower()==baseparent.lower():
            print 'Updating location...'
            relpath=parent
            parent=''

        pageID=self.__getPageID(server, token, relpath)

        if pageID is not None:
            page = server.confluence1.getPage(token, pageID)
            page['content']=content
            newpage = server.confluence1.storePage(token, page)
            print 'Page Successfully updated: %s, %s' % (newpage['title'], len(content))
        else:
            newpagedata = {"title":basename, "content":content,"space":self.space}

            if len(parent)>0:
                parentID=self.__getPageID(server, token, parent)
                print('parent: %s, %s' % (parentID, parent))
                if parentID is not None:
                    parentpage = server.confluence1.getPage(token, parentID);

                    if parentpage is None:
                        print('ERROR: parent  not found: %s, %s!' % (self.space, parent))
                    else:
                        newpagedata['parentId']=parentpage['id']

            self.__renameOldDuplicates(server, token, basename)

            newpage = server.confluence1.storePage(token, newpagedata)
            print 'Page Successfully Created: %s, %s' % (newpage['title'], len(content))

    def __getMimeType(self, ext):
        contentType='text/plain'

        if ext=='.txt':
            contentType='text/plain'
        elif ext=='.html':
            contentType='text/html'
        elif ext=='.jpeg' or ext=='.jpg':
            contentType='image/jpeg'
        elif ext=='.gif':
            contentType='image/gif'
        elif ext=='.png':
            contentType='image/png'
        elif ext=='.doc':
            contentType='application/msword'
        elif ext=='.docx' or ext=='.pptx' or ext=='.xlsx':
            contentType='application/vnd.openxmlformats'
        elif ext=='.xls' or ext=='.xlsx':
            contentType='application/vnd.ms-excel'
        elif ext=='.pdf':
            contentType='application/pdf'
        elif ext=='.zip':
            contentType='application/zip'
        elif ext=='.gzip' or ext=='.gz':
            contentType='application/x-gzip'
        elif ext=='.csv':
            contentType='text/csv'
        elif ext=='.xml':
            contentType='text/xml'
        elif ext=='.ogg':
            contentType='audio/ogg'
        elif ext=='mp3':
            contentType='audio/mpeg'
        elif ext=='.wav':
            contentType='audio/vnd.wave'
        elif ext=='.mp4':
            contentType='video/mp4'
        elif ext=='.mpeg' or ext=='.mpg':
            contentType='video/mpeg'
        elif ext=='.mov':
            contentType='video/quicktime'
	elif ext=='.sql':
             contentType='text/plain'
        elif ext=='.bat':
             contentType='text/plain'
        else:
            print 'ERROR: Unknown content type: %s' % ext

        return contentType

    def __loadAttachment(self, server, token, fpath):
        with open(fpath, 'rb') as f:
            data = f.read(); # slurp all the data

        relpath=fpath.replace(self.destination, '').strip('/')

        basename=os.path.basename(relpath)
        parent=os.path.dirname(relpath).strip('/')

        name, ext = os.path.splitext(relpath)

        contentType=self.__getMimeType(ext)

        try:
            pageID=self.__getPageID(server, token, parent)
            print('Attachment parent ID: %s' % pageID)

            if pageID is not None:
                attachment = {};
                attachment['fileName'] = basename
                attachment['contentType'] = contentType;

                print 'Reading binary: %s...' % len(data)
                bdata=xmlrpclib.Binary(data)

                print 'Uploading attachment: %s' % basename
                server.confluence1.addAttachment(token, pageID, attachment, bdata);

            else:
                print 'ERROR: Failed to locate parent: %s' % parent
        except Exception, e:
            print 'ERROR: Failed to load attacment: %s' % basename
            print 'EXCEPTION: %s\n' % unicode(str(e))

        f.close()

if __name__ == "__main__":
    if len(sys.argv)<=5:
        print '\nUsage: h2c.py [https://servername.com] [login] [password] [confluence-space] [source] [destination]\n'
        print 'Example: ./htc.py https://server.com user test spacename source converted\n'
    else:
        c = H2C()

        c.setServer(sys.argv[1])
        c.setUser(sys.argv[2])
        c.setPass(sys.argv[3])
        c.setSpace(sys.argv[4])
        c.setSource(sys.argv[5])
        c.setDestination(sys.argv[6])

        if c.process():
#            c.loadPages()
            print '\nIMPORT COMPLETE.\n'
