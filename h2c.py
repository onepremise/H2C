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
import traceback
import re
import string
import os
from html2textile import html2textile
import shutil
import xmlrpclib
from xmlrpclib import Server
from collections import deque
import urlparse
import dav
import urllib
import filecmp

try:
    False
    True
except NameError:
    True = 1
    False = not True
    pass

BLOCK_SIZE =  1048576 * 16

# Export/Import class for exporting contents, converting HTML, and importing 
# content.
class H2C:
    def __init__(self):
        self.action=''
        self.server=''
        self.webdav=''
        self.login=''
        self.passwd=''

        self.space='default'

        self.isource='source'
        self.idestination='converted'

        self.esource='remote-source'
        self.edestination='exported-data'

        self.attachements='attachments'

        self.linksToReplace=[]
        self.imagesToReplace=[]

    def setServer(self, s):
        self.webdav=s
        self.server=s

        if self.action=='import' or self.action=='convert':
            self.webdav=self.server+'/plugins/servlet/confluence/default/Global'
            self.server=self.server+'/rpc/xmlrpc'

    def setAction(self, a):
        self.action=a

    def setUser(self, u):
        self.login=u

    def setPass(self, p):
        self.passwd=p

    def setSpace(self, s):
        self.space=s

    def setImportSource(self, s):
        self.isource=s

    def setImportDestination(self, d):
        self.idestination=d

    def setExportSource(self, s):
        self.esource=s

    def setExportDestination(self, d):
        self.edestination=d
        
    # Create necessary project directories for Import
    def __initializeImportEnvironment(self):
        if not os.path.exists(self.idestination):
            print 'Creating destination: %s' % self.idestination
            os.makedirs(self.idestination)

    # Create necessary project directories for Export
    def __initializeExportEnvironment(self):
        if not os.path.exists(self.edestination):
            print 'Creating destination: %s' % self.edestination
            os.makedirs(self.edestination)

    # Export content from webdav
    def exportContent(self):
        self.__initializeExportEnvironment()

        print 'Exporting content from %s' % self.server
        try:
            filename=os.path.basename(self.esource)

            o = urlparse.urlparse(self.server)
     
            if o.scheme=='http':
                print 'Attempting authentication with webdav...'
                conn = dav.DAVConnection(o.netloc)
            elif o.scheme=='https':
                print 'Attempting authentication with secure webdav...'
                conn = dav.DAVSConnection(o.netloc)

            conn.set_auth(self.login, self.passwd)

            response = conn.options(self.esource)

            if response.status != 200:
                print 'Attempting authentication with NTLM...'
    
                conn = dav.SharePointDAVConnection(o.netloc)

                conn.set_auth(self.login, self.passwd)

            if response.status != 200:
                print 'Connection Authenticated.'
                self.__exportWebDAVDir(conn, self.esource)
            else:
                print 'ERROR: Failed to authenticate! Please check your login.'
                return False
                
            return True
        except Exception, e:
            print 'ERROR: Failed to export webdav: %s' % self.server
            print 'EXCEPTION: %s\n' % e
            traceback.print_exc(file=sys.stdout)
            return False
            
        return True
    
    # Check for directory names like 1. Analysis or 2. Data         
    def __isProjectDir(self, directory):
        pattern = re.compile('[12345]\. .+?\/')
        m = pattern.search(directory)
                
        if m==None:
            pattern = re.compile('[12345]\. .*')
            m = pattern.search(directory)        
            
        if m!=None:
            return True
            
        return False
    
    # Don't use directory names like 1. Analysis or 2. Data    
    def __stripProjectSubDir(self, c):
        pattern = re.compile('[12345]\. .+?\/')
        m = pattern.search(c)
                
        if m==None:
            pattern = re.compile('[12345]\. .*')
            m = pattern.search(c)
            
        if m==None:
            return c
            
        localpath=c
        localpath=localpath.replace(m.group(0), '')
        localpath=localpath.replace('//', '/')
        localpath=localpath.rstrip(os.sep)
        
        return localpath

    # Recursive interation over child drectories and contents
    def __exportWebDAVDir(self, conn, directory):
        try:
            print 'Exporting directory=%s' % directory
            
            parent=self.edestination+directory
            isParentProjSubDir=self.__isProjectDir(parent)
            parent=self.__normalizeString(parent, 0)
            
            if not os.path.exists(parent) and not isParentProjSubDir:
                os.makedirs(parent)

            do = dav.DAVCollection(directory, conn)

            cnames = sorted(do.get_child_names())
            
            if not (self.__isProjectDir(os.path.basename(directory))):
                self.__createBrowsePage(False, True, directory, cnames)
            else:
                self.__createBrowsePage(True, True, directory, cnames)

            for c in cnames:
                node=self.server+c
                localpath=self.edestination+c

                do = dav.DAVResource(node, conn)

                is_collection=do.is_collection()

                if self.__isProjectDir(c):
                    localpath=self.__stripProjectSubDir(localpath)
                    
                localpath=self.__normalizeString(localpath, 0)

                if is_collection:
                    if not os.path.exists(localpath):
                        os.mkdir(localpath)

                    if c != directory:
                    	self.__exportWebDAVDir(conn, c)
                else:
                    #recreate file
                    print 'Downloading File %s to %s...' % (node, localpath)
                    self.__recieveFile(do.get(), localpath)
        except Exception, e:
            print 'ERROR: Failed to export webdav: %s' % self.server
            print 'EXCEPTION: %s\n' % e
            traceback.print_exc(file=sys.stdout)

    # Create a browse page for navigation in confluence
    def __createBrowsePage(self, appendPage, stripPage, directory, cnames):
        print 'Creating browse page for directory=%s' % directory
        if directory=='/':
            basedir=os.sep + self.edestination
            print 'basedir=%s' % basedir
            filename = self.edestination + basedir
            localpath=filename
        else:
            basedir = os.path.basename(directory)
            filename = self.edestination + directory + os.sep + basedir
        
        if stripPage and directory!='/':
            localpath=self.__stripProjectSubDir(directory)
            filename = self.edestination + localpath + os.sep + os.path.basename(localpath)
        
        localpath=self.__normalizeString(localpath, 0)
        filename=self.__normalizeString(filename, 0)
        
        localfile = open(filename, 'a')

        if not appendPage:
            localfile.seek ( 0, 0 )
            formattedDir=localpath.replace(os.sep, ' > ')
            
            if directory=='/':
                localfile.write('h2. %s > %s >\n\n' % (self.space, self.edestination))
            else:
                localfile.write('h2. %s > %s %s >\n\n' % (self.space, self.edestination, formattedDir))
                
            localfile.flush()
            localfile.seek ( 0, 2 )

        for c in cnames:
            if c != directory:
                if not self.__isProjectDir(os.path.basename(c)):
                    c=self.__stripProjectSubDir(c)
                    c=self.__normalizeString(c, 0)
                    basename, ext = os.path.splitext(c)
                    
                    if len(ext)==0:
                        newpath=os.path.basename(c)
                        newpath=newpath.replace(' ', '')
                        localfile.write(' * [%s:%s]\n' % (self.space, newpath))
                    else:
                        newpath=os.path.basename(c)
                        newpath=newpath.replace(' ', '')
                        localfile.write(' * [^%s]\n' % newpath)

        localfile.close()
        
    def __recieveFile(self, response, localPath):
        local_file = open(localPath, "w")
        
        length=response.getheader('content-length')
        
        if length is not None:
            length=int(length)
            print 'Reading Bytes=%d' % length
            while length > BLOCK_SIZE: 
                data = response.read(BLOCK_SIZE) 
                length -= BLOCK_SIZE
                local_file.write(data)
                print 'Remainding Bytes=%d' % length

            data = response.read(length)
            local_file.write(data)
        else: 
            data = response.read()
            local_file.write(data)
                    
        local_file.close()

    def __testXmlRPCConnection(self):
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
        value=value.replace('[', '')
        value=value.replace(']', '')        
        value=value.replace(' ', '')

        return value

    def __matchNormalizedString(self, path, useTitle=0):
        components = path.split(os.sep)
        newpath=''

        for c in components:
            if c != self.idestination and c != self.attachements:
                c=self.__normalizeString(c, not c[0].isupper())
            newpath=os.path.join(newpath,c)

        return newpath

    # Convert HTML to Confluence Textile for import
    def convertContent(self):
        if not self.__testXmlRPCConnection():
            return False

        self.__initializeImportEnvironment()

        self.attachements=os.path.join(self.idestination, self.attachements)
            
        if not os.path.exists(self.attachements):
            print 'Creating destination: %s' % self.attachements
            os.makedirs(self.attachements)

        self.__convertContents(self.isource, 1)
        self.__processLinks()
        self.__processImages()

        return True
        
    def __convertContents(self, dir, recreateFullPath):
        for root, subFolders, files in os.walk(dir):
            for folder in subFolders:
               # folder=self.__normalizeString(folder)
                if recreateFullPath:
                    d=os.path.join(root,folder)
                else:
                    d=''

                newd=os.path.join(self.idestination,d)

                newd=self.__matchNormalizedString(newd, 1)

                if not os.path.exists(newd):
                    print 'Createing directory=%s' % newd
                    os.makedirs(newd)

            for file in files:
                skipCopy=False
                
                f=os.path.join(root,file)
                basename, extension = os.path.splitext(f)

                if not recreateFullPath:
                    basename=os.path.basename(basename)

                basename=os.path.join(self.idestination, basename)

                if (extension == '.html'):
                    self.__convertFile(f,basename)
                    print '\n'
                else:
                    if recreateFullPath:
                        newf=basename+extension.lower()
                        newf=self.__matchNormalizedString(newf, 1)
                        
                        if os.path.exists(newf) and filecmp.cmp(f, newf):
                            skipCopy=True
                            
                        if not skipCopy:
                            print 'Copying File: %s...' % f
                            shutil.copyfile(f, newf)    
                    else:
                        basename=os.path.basename(file)
                        attachment=os.path.join(self.attachements,basename)
                        attachment=self.__matchNormalizedString(attachment, 0)
                        
                        if os.path.exists(attachment) and filecmp.cmp(f, attachment):
                            skipCopy=True
                            
                        if not skipCopy:
                            print 'Copying Attachment: %s...' % f
                            shutil.copyfile(f, attachment)

                    #if (extension in ['.jpg', 'gif']):
                    #    self.imagesToReplace .append(f)

    def __globalImageReplace(self, image):
        basename=os.path.basename(image)
        for dname, dirs, files in os.walk(self.idestination):
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
        updatedSource=f.replace(self.isource, '')
        updatedDest=fdestination.replace(self.idestination, '')
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
        for dname, dirs, files in os.walk(self.idestination):
            for fname in files:
                basename, ext = os.path.splitext(fname)
                
                if ext == '':
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

    # String html extention from content
    def __stripHtmlExt(self, url, content):
        newVal=string.replace(url, '.html', '')
        p = re.compile(url)
        content=p.sub(newVal, content)
        return content

    # String localhost from content
    def __stripLocalhost(self, url, content):
        p = re.compile('http:\/\/localhost.+?\/')
        content=p.sub('', content)
        return content
        
    # If an error occurs through Remote API, you must restart connection
    def __resetConnection(self, s, token):
        print 'Restablishing Connection...'
        
       # s.confluence1.logout(token)
        
        s = Server(self.server)
        
        token = s.confluence1.login(self.login, self.passwd)
        
        print 'Connection Established.'
        
        return s, token

    # Import content using xmlrpc and webdav
    def importContent(self):
        s = Server(self.server)
        token = s.confluence1.login(self.login, self.passwd)
        
        self.__remoteMkDirs(s, token, self.idestination)

        destList=os.walk(self.idestination)
        for root, subFolders, files in os.walk(self.idestination):
            for folder in subFolders:
                dpath=os.path.join(root,folder).replace('(','').replace(')','')
                self.__createDir(s, token, dpath)
            for fle in files:
                fullrelpath = os.path.join(root, fle).replace('(','').replace(')','')
                basename, ext = os.path.splitext(fullrelpath)

                if ext == '':
                    self.__loadPage(s, token, fullrelpath)
                else:
                    self.__loadAttachment(s, token, fullrelpath)
		
        return True
    
    # Recursively create full remote path    
    def __remoteMkDirs(self, server, token, path):
        print 'Creating full path: %s...' % path
        
        nextpath = []
        components = deque(path.strip('/').split(os.sep))

        while len(components) > 0:
            c=components.popleft()
        
            nextpath.append(c)
            
            builtpath=os.path.join(*nextpath)
        
            print 'Verifying: %s...' % builtpath
            pID=self.__getPageID(server, token, builtpath)
        
            if pID==None:
                self.__createDir(server, token, builtpath)
        

    # Get the actual page ID with the correct path
    def __getPageID(self, server, token, parent, parentID=None):
        components = deque(parent.split(os.sep))

        c=components.popleft()
        
        try:
            if parentID == None:
                try:
                    page = server.confluence1.getPage(token, self.space, c)
                except Exception, e:
                    return None
            else:
                page = server.confluence1.getPage(token, parentID)

            pagesummaries = sorted(server.confluence1.getChildren(token, page['id']))

            if len(components)>0 and pagesummaries is not None:
                if len(pagesummaries)>0:
                    for ps in pagesummaries:
                        pagename=self.__stripUniqueID(ps['title'])
                        #print 'pagename=%s, ps[title]=%s, components[0]=%s' % (pagename,ps['title'],components[0])
                        if pagename == components[0]:
                            components[0]=ps['title']
                            nextpath=os.path.join(*components)
                            #print 'after nextpath=%s, %s' % (nextpath, ps['title'])
                            return self.__getPageID(server,token,nextpath,ps['id'])
                    return None
            elif len(components) == 0:
                return page['id']
        except Exception, e:
            print('ERROR: Parent parse failed: %s, %s' % (self.space,c))
            print('EXCEPTION %s' % unicode(str(e)))
            return None
        
        return None
      
    # Sometimes duplicates exists and cause issues loading attachements    
    def __resolvePath(self, server, token, fpath):
        parentID=None
        base=os.path.basename(fpath)
        path=os.path.dirname(fpath)
        nextpath = []
        components = deque(path.split(os.sep))

        try:
            while len(components) > 0:
                c=components.popleft()
                
                if parentID == None:
                    try:
                        page = server.confluence1.getPage(token, self.space, c)
                        nextpath.append(page['title'])
                    except Exception, e:
                        return None
                else:
                    page = server.confluence1.getPage(token, parentID)      
            
                pagesummaries = sorted(server.confluence1.getChildren(token, page['id']))
                
                if pagesummaries is not None and len(pagesummaries)>0:
                    for ps in pagesummaries:
                        pagename=self.__stripUniqueID(ps['title'])
                        if pagename.lower() == components[0].lower():
                            nextpath.append(ps['title'])
                            parentID=ps['id']
                            break
            
            newpath=os.path.join(os.path.join(*nextpath),base)
            
            return newpath
        except Exception, e:
            print 'WARNING: Path not found, %s.' % path
            return fpath

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
            
    def __stripUniqueID(self, pagename):
        pattern = re.compile('_[0-9]*$')
        m = pattern.search(pagename)
            
        if m==None:
            return pagename
            
        pagename=pagename.replace(m.group(0), '')
        
        return pagename        
            
    def __getUniqueConfluencePageName(self, server, token, pagename):
        count=1
        page=None

        try:
            originalpage = server.confluence1.getPage(token, self.space, pagename)

            if originalpage is None:
                return pagename
        except:
            return pagename

        while page is None:
            nextpagename=pagename+'_'+str(count)

            try:
                testpage = server.confluence1.getPage(token, self.space, nextpagename)
            except:
                testpage = None

            if testpage is None:
                page=nextpagename

            count+=1
            
        return page
            
    def __createDir(self, server, token, dpath):
        dpath=dpath.strip('/')
        basename=os.path.basename(dpath)
        parent=os.path.dirname(dpath)
        parentID = None
        
        print('Checking for remote directory: "%s"' % dpath)
        
        if len(parent)>0:
            parentID=self.__getPageID(server, token, parent)
            print 'Parent ID=%s' % parentID

        newDirID=self.__getPageID(server, token, dpath)

        if newDirID is not None:
            print 'Directory exist already: %s; skipping...\n' % basename
            return

        pagename=self.__getUniqueConfluencePageName(server, token, basename)
        
        newpagedata = {"title":pagename, "content":" ","space":self.space}

        if parentID is not None:
            print 'Assigning parentID: %s' % parentID
            newpagedata['parentId']=parentID
        try:
            print 'Creating remote directory: "%s, %s"' % (parentID, newpagedata['title'])
            newpage = server.confluence1.storePage(token, newpagedata)
            print 'Successfully created: %s\n' % newpage['title']
        except Exception, e:
            print 'ERROR: Failed to create %s' % basename
            print('EXCEPTION: %s\n' % unicode(str(e)))
            traceback.print_exc(file=sys.stdout)

                
    def __loadPage(self, server, token, fpath):
        f=open(fpath, 'rb')
        f.seek(0)
        content=f.read()
        f.close()
        
        fpath=fpath.strip('/') 

        basename=os.path.basename(fpath)
        parent=os.path.dirname(fpath).strip('/')

        baseparent=os.path.basename(parent)
        
        #check to see if it's a renamed browse-page and/or parent page
        relpath=fpath
        
        print'Loading page, parent=%s, page=%s...' % (parent, basename)
        
        try:
            if self.__stripUniqueID(basename.lower())==self.__stripUniqueID(baseparent.lower()):
                print 'Parent and Page match, updating...'
                relpath=parent
                parent=os.path.dirname(relpath).strip('/')
                print 'Updated location, parent=%s, page=%s.' % (parent, relpath)

            pageID=self.__getPageID(server, token, relpath)
            
            print 'pageID=%s' % pageID

            if pageID is not None:
                page = server.confluence1.getPage(token, pageID)
                page['content']=content
                newpage = server.confluence1.storePage(token, page)
                print 'Page Successfully updated: %s, %s\n' % (newpage['title'], len(content))
            else:
                pagename=self.__getUniqueConfluencePageName(server, token, basename)
                newpagedata = {"title":pagename, "content":content,"space":self.space}

                if len(parent)>0:
                    parentID=self.__getPageID(server, token, parent)
                    print('parent: %s, %s' % (parentID, parent))
                    if parentID is not None:
                        parentpage = server.confluence1.getPage(token, parentID);

                        if parentpage is None:
                            print('ERROR: parent  not found: %s, %s!' % (self.space, parent))
                        else:
                            newpagedata['parentId']=parentpage['id']
            
                newpage = server.confluence1.storePage(token, newpagedata)
                print 'Page Successfully Created: %s, %s\n' % (newpage['title'], len(content))
        except Exception, e:
            print 'ERROR: Failed to create page: %s' % basename
            print('EXCEPTION: %s\n' % unicode(str(e)))
            traceback.print_exc(file=sys.stdout)
                
    def __getMimeType(self, ext):
        ext=ext.lower()
        contentType='text/plain'

        if ext=='.txt':
            contentType='text/plain'
        elif ext=='.cfg':
            contentType='text/plain'
        elif ext=='.html':
            contentType='text/html'
        elif ext=='.jpeg' or ext=='.jpg':
            contentType='image/jpeg'
        elif ext=='.gif':
            contentType='image/gif'
        elif ext=='.png':
            contentType='image/png'
        elif ext=='.doc' or  ext=='.dot':
            contentType='application/msword'
        elif ext=='.ppt':
            contentType='application/vnd.ms-powerpoint'    
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
        elif ext=='.dbf':
             contentType='application/dbase'
        elif ext=='.jar':
             contentType='application/java-archive'
        else:
            print 'WARNING: Unknown mime type: %s' % ext

        return contentType

    def __loadAttachment(self, server, token, fpath):
        print('loading attachment: %s...' % fpath)
        
        relpath=fpath.strip('/')
        basename=os.path.basename(relpath)
        parent=os.path.dirname(relpath).strip('/')

        if os.path.getsize(fpath)>8388608:
             self.__loadLargeAttachment(server, token, fpath)
             return

        with open(fpath, 'rb') as f:
            data = f.read(); # slurp all the data

        name, ext = os.path.splitext(relpath)

        contentType=self.__getMimeType(ext)

        try:
            pageID=self.__getPageID(server, token, parent)

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

    def __loadLargeAttachment(self, server, token, fpath):
        print 'Using Webdav to load %s' % fpath    
        
        url = self.webdav + '/' + self.space + '/' + \
            self.__resolvePath(server, token, fpath)
            
        basename=os.path.basename(fpath)

        if not os.path.exists(fpath):
            return False

        with open(fpath, 'rb') as f:
            data = f.read();
        
        f.close()

        name, ext = os.path.splitext(fpath)

        contentType=self.__getMimeType(ext)

        try:
            print 'url=%s' % url
            
            o = urlparse.urlparse(url)
     
            if o.scheme=='http':
                conn = dav.DAVConnection(o.netloc)
            elif o.scheme=='https':
                conn = dav.DAVSConnection(o.netloc)

            conn.set_auth(self.login, self.passwd)

            response = conn.options(url)

            if response.status != 200:
                raise Exception("%d, %s" % (response.status, response.reason))

            response = conn.put(o.geturl(), data, contentType)
            
            if response.status == 409:
                print 'Conflict encountered with %s, attempting to delete and retry.' % basename
                response = conn.delete(o.geturl())
                response = conn.put(o.geturl(), data, contentType)

            if response.status > 204:
                raise Exception("%d, %s" % (response.status, response.reason))

            print 'WebDav Import Successful.'
        except Exception, e:
            print 'ERROR: Failed to load attacment using webdav: %s' % basename
            print 'EXCEPTION: %s\n' % unicode(str(e))

if __name__ == "__main__":
    if len(sys.argv)<=4:
        print '\nUsage: h2c.py [action] [https://servername.com] [login] ' + \
              '[password] [confluence-space] [action specific options...]\n'
        print '  Where [action] can be one of the following:'
        print ''
        print '   * convert - convert HTML content to confluence accepted format'
        print '               specify additional parameters: [confluence-space] [local-source] [working-directory]' 
        print ''
        print '   * import  - import converted content or other local source to confluence'
        print '               specify additional parameters: [confluence-space] [local-source]'  
        print ''      
        print '   * export  - export content from webdav/sharepoint'
        print '               specify additional parameters: [confluence-space] [remote-path] [exported-data]\n'
        print ''
        print 'Example: ./htc.py import https://server.com user test spacename /source /converted\n'
        print 'Example: ./htc.py export https://server.com:8443 user test spacename /remote/directory\n'
    else:
        c = H2C()

        c.setAction(sys.argv[1])
        c.setServer(sys.argv[2])
        c.setUser(sys.argv[3])
        c.setPass(sys.argv[4])
        c.setSpace(sys.argv[5])

        if c.action=='convert':
            c.setImportSource(sys.argv[6])
            c.setImportDestination(sys.argv[7])

            if c.convertContent():
                print '\nCONVERSION  COMPLETE.\n'
        elif c.action=='import':
            c.setImportDestination(sys.argv[6])

            if c.importContent():
                print '\nIMPORT COMPLETE.\n'
        elif c.action=='export':
            c.setExportSource(sys.argv[6])
            c.setExportDestination(sys.argv[7])
            if c.exportContent():
                print '\nEXPORT COMPLETE.\n'
        else:
            print 'Please specify an accpeted [action]!'
