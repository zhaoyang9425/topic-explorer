#!/usr/bin/env python
from __future__ import absolute_import
from ConfigParser import RawConfigParser as ConfigParser
import httplib, ssl
import json
import os.path
from StringIO import StringIO ## used to stream http response into zipfile.
import sys
from time import sleep
from urllib2 import urlopen
from urllib import quote_plus, urlencode
from zipfile import ZipFile  ## used to decompress requested zip archives.

from topicexplorer.lib.util import *

def metadata(id, sleep_time=1):
    solr ="http://chinkapin.pti.indiana.edu:9994/solr/meta/select/?q=id:%s" % id
    solr += "&wt=json" ## retrieve JSON results
    # TODO: exception handling
    if sleep_time:
        sleep(sleep_time) ## JUST TO MAKE SURE WE ARE THROTTLED
    try:
        data = json.load(urlopen(solr))
        print id
        return data['response']['docs'][0]
    except ValueError :
        print "No result found for " + id 
        return dict()

def get_metadata(folder):
    ids = os.listdir(folder)
    data = [(id.strip(), metadata(id.strip())) for id in ids]
    data = dict(data)
    with open(os.path.join(folder, '../metadata.json'),'wb') as outfile:
        json.dump(data, outfile)
    


"""
DOWNLOAD VOLUMES
Code to download volumes
"""
host = "silvermaple.pti.indiana.edu" # use over HTTPS
port = 25443
oauth2EPRurl = "/oauth2/token"
oauth2port = 9443
dataapiEPR = "/data-api/"


## getVolumesFromDataAPI : String, String[], boolean ==> inputStream
def getVolumesFromDataAPI(token, volumeIDs, concat=False):
    data = None

    assert volumeIDs is not None, "volumeIDs is None"
    assert len(volumeIDs) > 0, "volumeIDs is less than one"
    
    url = dataapiEPR + "volumes"
    data = {'volumeIDs' : '|'.join(volumeIDs)}
    if concat:
        data['concat'] = 'true'

    headers = {"Authorization" : "Bearer " + token,
               "Content-type" : "application/x-www-form-urlencoded"}

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    httpsConnection = httplib.HTTPSConnection(host, port,
        context=ctx)
    httpsConnection.request("POST", url, urlencode(data), headers)

    response = httpsConnection.getresponse()

    if response.status is 200:
        data = response.read()
    else:
        print "Unable to get volumes"
        print "Response Code: ", response.status
        print "Response: ", response.reason
        
    if httpsConnection is not None:
        httpsConnection.close()

    return data

def getPagesFromDataAPI(token, pageIDs, concat):
    data = None

    assert pageIDs is not None, "pageIDs is None"
    assert len(pageIDs) > 0, "pageIDs is less than one"
    
    url = dataapiEPR
    url = url + "pages?pageIDs=" + quote_plus('|'.join(pageIDs))

    if (concat):
        url = url + "&concat=true"

    print "data api URL: ", url
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    httpsConnection = httplib.HTTPSConnection(host, port, context=ctx)

    headers = {"Authorization" : "Bearer " + token}
    httpsConnection.request("GET", url, headers=headers)

    response = httpsConnection.getresponse()

    if response.status is 200:
        data = response.read()
    else:
        print "Unable to get pages"
        print "Response Code: ", response.status
        print "Response: ", response.reason
        
    if httpsConnection is not None:
        httpsConnection.close()

    return data

    
def obtainOAuth2Token(username, password):
    token = None
    url = None
    httpsConnection = None
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    httpsConnection = httplib.HTTPSConnection(host, oauth2port, context=ctx)

    url = oauth2EPRurl
    ## make sure to set the request content-type as application/x-www-form-urlencoded
    headers = {"Content-type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type" : "client_credentials",
        "client_secret" : password,
        "client_id" : username
        }
    data = urlencode(data)
    print data 

    ## make sure the request method is POST
    httpsConnection.request("POST", url + "?" + data, "", headers)

    response = httpsConnection.getresponse()

    ## if response status is OK
    if response.status is 200:
        data = response.read()

        jsonData = json.loads(data)
        print"*** JSON: ", jsonData
        
        token = jsonData["access_token"]
        print "*** parsed token: ", token
        

    else:
        print "Unable to get token"
        print "Response Code: ", response.status
        print "Response: ", response.reason
        print response.read()

    if httpsConnection is not None:
        httpsConnection.close()
        
    return token

def printZipStream(data):
    # create a zipfile from the data stream
    myzip = ZipFile(StringIO(data))

    #iterate over all items in the data stream
    for name in myzip.namelist():
        print "Zip Entry: ", name
        # print the file contents
        print myzip.read(name)

    myzip.close()

def download(args):
    # extract files
    with open(args.file) as IDfile:
        volumeIDs = [line.strip() for line in IDfile]
    # create output folder, if nonexistant
    if not os.path.isdir(args.output):
        os.makedirs(args.output)

    if not args.username and not args.password:
        path = os.path.expanduser('~')
        path = os.path.join(path, '.htrc')
	config = ConfigParser(allow_no_value=True)
        if os.path.exists(path):
	    config.read(path)
            if config.has_section('main'):
                args.username = config.get("main", "username")
                args.password = config.get("main", "password")

        # If config file is blank, still prompt!
        if not args.username and not args.password:
            print "Please enter your HathiTrust credentials."
            args.username = raw_input("Token: ")
            args.password = raw_input("Password: ")
            save = bool_prompt("Save credentials?", default=True)
            if save:
                with open(path, 'w') as credential_file:
                    if not config.has_section('main'):
                        config.add_section('main')
                    config.set('main', 'username', args.username)
                    config.set('main', 'password', args.password)
                    config.write(credential_file)
    

    token = obtainOAuth2Token(args.username, args.password)
    if token is not None:
        print "obtained token: %s\n" % token
        ## to get volumes, uncomment next line
        data = getVolumesFromDataAPI(token, volumeIDs, False)

        ## to get pages, uncomment next line
        #data = getPagesFromDataAPI(token, pageIDs, False) 

        myzip = ZipFile(StringIO(data))
        myzip.extractall(args.output)
        myzip.close()
    else:
        print "Failed to obtain oauth token."
        sys.exit(1)


def main():
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parsers = parser.add_subparsers(help="select a command")
    
    # Metadata Helpers
    parser_getmd = parsers.add_parser('get-md', 
        help="Get metadata for a folder of HathiTrust volumes")
    parser_getmd.add_argument("folder", nargs="?", 
        type=lambda x: is_valid_filepath(parser_getmd, x),
        help="Path to Config [optional]")
    parser_getmd.set_defaults(func='getmd')
    
    # Download Helper
    parser_download = parsers.add_parser('download', 
        help="Download HathiTrust volumes to disk [requires auth]")
    parser_download.add_argument("-u", "--username", help="HTRC username")
    parser_download.add_argument("-p", "--password", help="HTRC password")
    parser_download.add_argument("file", help="input file of ids",
        type=lambda x: is_valid_filepath(parser_download, x))
    parser_download.add_argument("-o", "--output", required=True, help="output directory")
    parser_download.set_defaults(func='download')

    args = parser.parse_args()

    if args.func == 'getmd':
        get_metadata(args.folder)
    if args.func == 'download':
        download(args)

if __name__ == '__main__':
    main()
