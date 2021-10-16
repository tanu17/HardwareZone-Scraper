
# -*- coding: utf-8 -*-
import scrapy
import requests, re
import ast, datetime

class hwZoneSpider(scrapy.Spider):
    name = 'hwZoneScraper'
    login_url = 'https://forums.hardwarezone.com.sg/login/login'
    start_urls = [login_url]

    domain = 'https://forums.hardwarezone.com.sg/'
    redirect_url = 'https://forums.hardwarezone.com.sg/search/?type=post'
    search_url = 'https://forums.hardwarezone.com.sg/search/search'

    token = ''

    # Payload data
    login_uname = 'DisinfoResearch'
    password = '27xts79SzpHV8bL!'
    search = 'ivermectin'
    start_date = '2021-01-01' # yyyy-mm-dd
    end_date = '2021-10-16'

    post_id_dict = {}
    thread_num = 0


    def start_requests(self):
        urls = [self.login_url]
        yield scrapy.Request(url = urls[0], callback = self.login_with_credentials)


    def login_with_credentials(self, response):
        self.token = response.css('input[name="_xfToken"]::attr(value)').extract_first()
        login_payload = {
        'login' : self.login_uname,
        'password' : self.password,
        'remember': '1',
        '_xfRedirect': '/',
        '_xfToken': self.token
        }

        return scrapy.FormRequest(
            url =self.login_url,
            formdata=login_payload,
            callback=self.after_login)


    def after_login(self, response):
        if "Incorrect password" in response.text:
            self.log("\nLogin failed: Incorrect password failure\n")
            return
        
        if "The requested user '%s' could not be found"%self.login_uname in response.text:
            self.log("\nLogin failed: User not found\n")
            return
        
        # Continue scraping with authenticated session
        self.log("Login successful")
        yield scrapy.Request(url=self.redirect_url, callback=self.search_config)


    def search_config(self, response):
        # Creating dictionary of payload configuration for form to be sent to server
        search_payload = {
            'keywords' : self.search,
            'c[users]' : '',
            'c[newer_than]': self.start_date,
            'c[older_than]': self.end_date,
            'c[min_reply_count]': '0',
            'c[nodes][]': '',
            'c[child_nodes]': '1',
            'order': 'date',
            'grouped': '1',
            'search_type': 'post',
            '_xfToken': self.token,
            '_xfRequestUri': '/search/?type=post',
            '_xfWithData': '1',
            '_xfToken': self.token,
            '_xfResponseType': 'json',
        }
        
        yield scrapy.FormRequest(
            url=self.search_url,
            formdata=search_payload,
            callback=self.search_redirect)


    def search_redirect(self, response):
        if 'No results found' in response.text:
            self.log("\nNo result found for search string\n")
            return

        self.log("Search results found")
        # Extracting the redirect url from the response
        for response_text in response.text.split("\n"):
            if 'redirect' in response_text:
                str_rem = '    "redirect": '
                redirect_main_url = response_text.strip(str_rem).strip('",')

        self.log("Redirecting to search results")
        yield scrapy.Request(url=redirect_main_url, callback=self.parse)


    def parse(self, response):
        for thread in response.css('div.contentRow-main'):

            self.thread_num += 1

            thread_url = thread.css('h3 > a::attr(href)').get()

            # THREAD INFO: title, name of forum the thread belongs to, time of thread creation, thread author details, thread url            
            thread_info = {
                # Get title of thread
                'title': thread.css('h3.contentRow-title > a::text').get().strip(), 
                # Get the last item in unordered list to get the forum/subforum that the thread belongs to 
                'forum_name' : (thread.css('li > a::text').getall())[-1], 
                # To convert to datetime object-> from datetime import datetime; datetime.strptime('2021-05-19T01:55:10+0800', '%Y-%m-%dT%H:%M:%S%z')
                'time_created' : thread.css('time::attr(datetime)').get(),
                'author' : { 'username': thread.css('a.username::text').get(), 'link_to_id': self.domain + response.css('a.username::attr(href)').get()},
                'url': self.domain + thread_url,
                'thread_num' : self.thread_num,
                # Number of posts in thread is number of replies in thread which helps to analyze thread traction
                'replies_count' : (thread.css('li::text').getall())[-2].replace('Replies: ',''),
            }

            # Parse the thread by caling parseThreads function on it
            yield response.follow(response.urljoin(thread_url), self.parseThreads, meta={'thread_info': thread_info})
        
        #next_page_alt = response.css("#forum > table:nth-last-child(9) > tr > td:nth-child(2) > div > ul > li:nth-last-child(2) > a::attr(href)").extract_first()

        # Extracting link to next page from next button in window
        next_page_search = response.css('a.pageNav-jump.pageNav-jump--next::attr(href)').get()
        if next_page_search is not None:
            next_page_search = response.urljoin(next_page_search)
            yield response.follow(next_page_search, self.parse)


    def parseThreads(self, response):

        thread_info = response.meta.get('thread_info')

        posts = response.css('article.message.message--post.js-post.js-inlineModContainer')
        for post in posts:

            # POST INFO: post content, post# in thread, reply_to, type of media and media link attached in the post, time of post creation, reactions, post url, post author details (name, link, user title, joined date, message#, reaction score)

            # From right top corner, we can obtain the post# in the thread and the post number 
            post_url = post.css('ul.message-attribution-opposite.message-attribution-opposite--list > li > a.message-attribution-gadget::attr(href)').get()
            if post_url is None:
                continue
            else:
                post_url = self.domain + post_url

            post_number = (post.css('ul.message-attribution-opposite.message-attribution-opposite--list > li > a::text').getall()[-1]).strip().replace('#','') 
            # Extract post id for the thread from post url
            post_id = str([int(s) for s in post_url.split('-') if s.isdigit()][0])

            # Adding post to dictionary of collection of posts and their link
            self.post_id_dict[post_id] = {'thread#': thread_info['thread_num'], 'post#': post_number}

            # A post can be a reply to another post in the thread
            try:
                replied_to_id = re.findall('\d+', post.css('a.bbCodeBlock-sourceJump::attr(data-content-selector)').get())
                if len(replied_to_id) == 1 :
                    try:
                        replied_to = self.post_id_dict[replied_to_id[0]]

                    # len > 0 and if key is not in dictionary, it implies that the post was deleted. div.bbCodeBlock-content or bbCodeBlock is in post.css to specify reply block and extract data from it
                    except Exception as e:
                        username_replied_to = (post.css('a.bbCodeBlock-sourceJump::text').get()).replace(' said:','')
                        content_replied_to = ''.join(post.css('div.bbCodeBlock-expandContent.js-expandContent::text').getall())
                        content_replied_to = ' '.join(content_replied_to.split())

                        video_link = post.css('div.bbCodeBlock-content > div.ytp-right-controls > a.ytp-youtube-button.ytp-button.yt-uix-sessionlink::attr(href)').getall()
                        if len(video_link)>0:
                            content_replied_to =  content_replied_to + "\n" + str(video_link)

                        article_link = post.css('div.bbCodeBlock.bbCodeBlock--unfurl.js-unfurl.fauxBlockLink::attr(data-url)').getall()
                        if len(article_link) >0 :
                            content_replied_to += "\nArticle linked in post- %s"%(article_link)
                        facebook_link = post.css('div.bbCodeBlock-content > div.fb-post.fb_iframe_widget::attr(data-href)').getall()
                        if len(facebook_link) >0 :
                            content_replied_to += "\nFacebook linked in post- %s"%(facebook_link)
                        tiktok_link = post.css('div.bbCodeBlock-content > video.video::attr(src)').getall()
                        if len(tiktok_link) >0 :
                                content_replied_to += "\nTikToks linked in post- %s"%(tiktok_link)
                        external_link = post.css('d div.bbWrapper > iframe::attr(src)').getall()
                        if len(external_link) >0 :
                                content_replied_to += "\nExternal links in post- %s"%(external_link)
                        replied_to = 'Replied to a deleted commented by %s- \n%s '%(username_replied_to,content_replied_to) 

                elif len(replied_to_id) == 0:
                    replied_to = ''
            except:
                 replied_to = ''


            # NOTE: 'div.bbWrapper ::text' and not 'div.bbWrapper::text' to extract text within <a> tag.
            # Alternate way- post.css('article.message-body > div.bbWrapper').xpath('string()').extract()
            post_content = ''.join(post.css('article.message-body > div.bbWrapper ::text').getall())
            post_content = ' '.join(post_content.split())

            post_bbWrapper = post.css('article.message-body.js-selectToQuote > div.bbWrapper')

            post_video_link = post_bbWrapper.css('head > link::attr(href)').getall()
            post_image_link = post_bbWrapper.css('img.bbImage::attr(data-url)').getall()
            post_fb_link = post_bbWrapper.css('div.fb-post.fb_iframe_widget::attr(data-href)').getall()
            post_external_link = post_bbWrapper.css('iframe::attr(src)').getall() + post_bbWrapper.css('a.link.link--external::attr(href)').getall()
            
            post_byline = post.css('aside > div.bbWrapper::text').get()

            post_time_created = post.css('time::attr(datetime)').get()

            # Only 6 reacts are available- Like, Love, Haha, Wow, Sad, Angry. Didn't follow link to extract as HWZ user's don't react often to post within thread and hence it is not a good indicator for post traction
            post_reactions_link = post.css('a.reactionsBar-link::attr(href)').get()
            if post_reactions_link is not None:
                post_reactions_link = self.domain + post_reactions_link
            else:
                post_reactions_link = ''

            post_author = {
                'name' : post.css('a.username::text').get(),
                'title' : post.css('h5.userTitle.message-userTitle::text').get(),
                'join_date' : post.css('dl.pairs.pairs--justified > dd::text').getall()[0],
                'message#' : post.css('dl.pairs.pairs--justified > dd::text').getall()[1],
                'reaction_score' : post.css('dl.pairs.pairs--justified > dd::text').getall()[2],
                'link' : self.domain + post.css('a.username::attr(href)').get()
            }

            yield {
                'thread_index' : thread_info['thread_num'],
                'post_index' : post_number,
                'thread_name' : thread_info['title'],
                'post_content' : post_content,
                'post_replied_to' : replied_to,
                'post_image_attached' : post_image_link,
                'post_video_link' : post_video_link,
                'post_fb_link' : post_fb_link,
                'post_external_link' : post_external_link,
                'post_author' : post_author,
                'post_created_at' : post_time_created,
                'thread_created_at' : thread_info['time_created'],
                'thread_replies_count' : thread_info['replies_count'],
                'thread_belongs_to_forum': thread_info['forum_name'],
                'thread_author' : thread_info['author'],
                'post_url' : post_url,
                'thread_url' : thread_info['url'],
                'post_reactions' : post_reactions_link,
                'post_byline' : post_byline,
            }

        next_page_thread = response.css('a.pageNav-jump.pageNav-jump--next::attr(href)').get()
        if next_page_thread is not None:
            next_page_thread = response.urljoin(next_page_thread)
            yield response.follow(next_page_thread, self.parseThreads, meta={'thread_info': thread_info})

        self.thread_num += 1
