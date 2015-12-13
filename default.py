import os
import urllib
import urllib2
import re
import json
import StorageServer
import xbmc
import xbmcplugin
import xbmcgui
import xbmcaddon
from urlparse import parse_qs, urlparse
import sys
# Do extra imports including from local addon dir
from bs4 import BeautifulSoup

__author__ = "divingmule, and Hans van den Bogert"
__copyright__ = "Copyright 2015"
__license__ = "GPL"
__version__ = "2"
__maintainer__ = "Hans van den Bogert"
__email__ = "hansbogert@gmail.com"

addon = xbmcaddon.Addon()
addon_profile = xbmc.translatePath(addon.getAddonInfo('profile'))
addon_version = addon.getAddonInfo('version')
addon_id = addon.getAddonInfo('id')
addon_dir = xbmc.translatePath(addon.getAddonInfo('path'))
sys.path.append(os.path.join(addon_dir, 'resources', 'lib'))


cache = StorageServer.StorageServer("engadget", 1)
icon = addon.getAddonInfo('icon')
language = addon.getLocalizedString
base_url = 'http://www.engadget.com'


def addon_log(string):

    """

    :type string: string
    """
    try:
        log_message = string.encode('utf-8', 'ignore')
    except UnicodeEncodeError:
        log_message = 'addonException: addon_log'
    xbmc.log("[%s-%s]: %s" % (addon_id, addon_version, log_message), level=xbmc.LOGDEBUG)


def make_request(url):
    addon_log('Request URL: %s' % url)
    headers = {
        'User-agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:24.0) Gecko/20100101 Firefox/24.0',
        'Referer': base_url
        }
    try:
        req = urllib2.Request(url, None, headers)
        response = urllib2.urlopen(req)
        data = response.read()
        response.close()
        return data
    except urllib2.URLError, e:
        addon_log('We failed to open "%s".' % url)
        if hasattr(e, 'reason'):
            addon_log('We failed to reach a server.')
            addon_log('Reason: %s' % e.reason)
        if hasattr(e, 'code'):
            addon_log('We failed with error code - %s.' % e.code)


def cache_categories():
    soup = BeautifulSoup(make_request(base_url + '/videos/'), 'html.parser')
    cat_items = soup.select('main section section')
    addon_log("more?")
    addon_log(str(cat_items[0].select("header a")[0].get('href')))
    cats = [{'name': i.select("h2")[0].string.strip(), 'href': i.select("header a")[0].get('href')} for i in cat_items]
    return cats


def display_all_items():
    feed_url = "http://feeds.contenthub.aol.com/syndication/2.0/feeds/article" \
        "?sid=6d83dd23075648c2924a6469c80026c7&articleText=7"
    s_data = make_request(feed_url)
    addon_log("AOL feed data:" + str(s_data))
    json_data = json.loads(s_data)

    # Big assumption here, the video is the 2nd item in the json list gotten by the AOL CDN
    item_tuples = [(x['title'],
                    x['media_content'][1]['media_html'],
                    x['media_content'][1]['url'],
                    x['media_content'][0]['url'])
                   for x in (json_data['channel']['item'])
                   if list_has_dict_with_video(x['media_content'])]
    for (title, embed_url, url, image) in item_tuples:
        add_dir(title, embed_url, url, image, 'resolve_url', False)


def list_has_dict_with_video(input):
    l = [y for y in input if y['media_medium'] == "video"]
    return len(l) > 0


def resolve_item(embed_url, url):
    domain = urlparse(url).netloc
    addon_log("Domain of media url is: " + domain)

    retrievers = {
        "on.aol.com": retrieve_url_for_aol,
        "www.youtube.com": retrieve_url_for_youtube,

    }
    retriever = retrievers.get(domain, lambda: nothing)

    addon_log("returning embed_url  and url for playback: " + embed_url + " " + url)
    return retriever(embed_url, url)


def nothing():
    return None


def retrieve_url_for_aol(embed_url, url):
    javascript_embed_tag = BeautifulSoup(embed_url, 'html.parser')
    addon_log(javascript_embed_tag)
    javascript_source = javascript_embed_tag.find('script').get('src')
    addon_log("javascript source from embed code" + str(javascript_source))
    javascript_blob = make_request(javascript_source)
    # addon_log("the javascript blob" + javascript_blob)
    pattern = re.compile('"videoUrls":\[".*?"\]')
    # Necessary dirty step, it's actually javascript, which happens to be JSON.
    s_urls = pattern.findall(javascript_blob)[0]
    # pre and post pend curly brace, to make it valid JSON
    s_urls_with_curly = "{" + s_urls + "}"

    addon_log("url strings retrieved from javascript blob: " + s_urls_with_curly)
    json_urls = json.loads(s_urls_with_curly)
    addon_log("Sending url to Kodi: " + json_urls['videoUrls'][0])
    return json_urls['videoUrls'][0]


def retrieve_url_for_youtube(embed_url, url):
    qs = parse_qs(urlparse(url).query)
    video_id = qs['v'][0]
    addon_log("Youtube videoId:" + video_id)
    return "plugin://plugin.video.youtube/?path=/root/video&action=play_video&videoid={0}".format(video_id)


def add_dir(name, embed_url, url, icon_image, dir_mode, is_folder=True):
    dir_params = {'name': name, 'embed_url': embed_url, 'url': url, 'mode': dir_mode}
    url = '%s?%s' % (sys.argv[0], urllib.urlencode(dir_params))
    list_item = xbmcgui.ListItem(name, iconImage="DefaultFolder.png", thumbnailImage=icon_image)
    if not is_folder:
        list_item.setProperty('IsPlayable', 'true')
    list_item.setInfo(type="Video", infoLabels={'Title': name})
    xbmcplugin.addDirectoryItem(int(sys.argv[1]), url, list_item, is_folder)


def get_params():
    p = parse_qs(sys.argv[2][1:])
    for i in p.keys():
        p[i] = p[i][0]
    return p


def main():
    params = get_params()
    addon_log(repr(params))

    mode = params.get('mode')

    if mode is None:
        display_all_items()
        xbmcplugin.endOfDirectory(int(sys.argv[1]))

    elif mode == 'resolve_url':
        success = False
        resolved_url = resolve_item(params['embed_url'], params['url'])
        if resolved_url:
            success = True
        else:
            resolved_url = ''
        item = xbmcgui.ListItem(path=resolved_url)
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), success, item)

if __name__ == "__main__":
    main()
