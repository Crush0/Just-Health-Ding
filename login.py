# -*- coding:UTF-8 -*-
from email.mime.text import MIMEText
from email.header import Header
import requests
import time
import json
import pymysql
import threading
import logging
from bs4 import BeautifulSoup
import smtplib
from apscheduler.schedulers.blocking import BlockingScheduler


class sendEmailThread(threading.Thread):
    def __init__(self, stu_id, is_success):
        threading.Thread.__init__(self)
        self.stu_id = stu_id
        self.is_success = is_success

    def run(self):
        send(self.stu_id, self.is_success)


# 所有用户的账号密码字典
userList = {}
mail_host = "smtp.xx.com"  # 设置服务器
mail_user = "xx@xx.com"  # 用户名
mail_pass = "xxxxxxxx"  # 口令
sender = 'xx@xx.com'


def send(stu_id, is_success):
    server = smtplib.SMTP_SSL(mail_host, 465)
    server.login(mail_user, mail_pass)
    sql = 'select address from stu_info where student_id=' + '\'' + stu_id + '\''
    db = pymysql.connect(host="xxxx", user="xx",
                         password="xxxx", db="xxxx", port=3306, charset='utf8')
    cur = db.cursor()
    try:
        cur.execute(sql)
        results = cur.fetchall()
        address = results[0][0]
        if is_success:
            message = MIMEText(stu_id + '打卡成功', 'plain', 'utf-8')
        else:
            message = MIMEText(stu_id + '打卡失败，请您手动打卡', 'plain', 'utf-8')
        message['From'] = Header("自动打卡", 'utf-8')
        message['To'] = Header(stu_id, 'utf-8')
        subject = '自动打卡提醒邮件'
        message['Subject'] = Header(subject, 'utf-8')
        server.sendmail(mail_user, address, message.as_string())
        logging.info('发送邮件成功')
    except Exception:
        logging.warning('发送邮件失败')
    db.close()
    server.close()


def main():
    connect()
    for key in userList:
        try:
            autoClockIn(key, userList[key])
            thread = sendEmailThread(key, True)
            thread.start()
            thread.join()
        except Exception as ex:
            logging.warning('+-----------------------+')
            logging.warning('+学号:\t' + key + '\t出现异常+\r\n')
            logging.warning('+' + ex.__str__() + '+')
            logging.warning('+-----------------------+')
            thread = sendEmailThread(key, False)
            thread.start()
            thread.join()
            continue


# 连接数据库获得用户字典
def connect():
    sql = 'select student_id,pwd from stu_info'
    logging.info('连接数据库')
    db = pymysql.connect(host="xxxx", user="xxx",
                         password="xxxxxx", db="xxxxx", port=22505, charset='utf8')
    cur = db.cursor()
    try:
        cur.execute(sql)
        results = cur.fetchall()
        for row in results:
            newone = {row[0]: row[1]}
            userList.update(newone)
    except Exception as e:
        logging.error('数据库连接失败' + e)
        exit(1)
    finally:
        db.close()


def autoClockIn(key, pwd):
    requests.packages.urllib3.disable_warnings()
    logging.info('学号' + key + "打卡进行中......")
    session = requests.session()
    # 响应头
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,'
                  'application/signed-exchange;v=b3;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Connection': 'keep-alive',
        'sec-ch-ua': '"Chromium";v="92", " Not A;Brand";v="99", "Google Chrome";v="92"',
        'sec-ch-ua-mobile': '?0',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/92.0.4515.131 Safari/537.36'
    }
    baseUrl = "http://my.just.edu.cn/"
    baseRequest = session.get(baseUrl, headers=headers, allow_redirects=False, verify=False)
    # 获得CAS认证服务器地址
    reUrl = baseRequest.headers["location"]
    cas_Response = session.get(reUrl, allow_redirects=False, verify=False)
    # 跳转直到登陆界面
    t = 0
    while cas_Response.status_code != 200:
        t += 1
        reUrl = cas_Response.headers["location"]
        cas_Response = session.get(reUrl, allow_redirects=False, verify=False)
        if t >= 10:
            logging.warning('跳转失败,当前url为:' + cas_Response.url)
            break
    # 在网页源代码中获得execution
    soup = BeautifulSoup(cas_Response.text, 'lxml')
    execution = soup.select_one('#fm1 > div:nth-child(5) > input[type=hidden]:nth-child(1)').get('value')
    data = {
        'username': key,
        'password': pwd,
        'execution': execution,
        '_eventId': 'submit',
        'loginType': '1',
        'submit': '%E7%99%BB+%E5%BD%95'
    }
    auth_response = session.post(reUrl, data=data, allow_redirects=False, verify=False)
    if auth_response.status_code == 200:
        soup = BeautifulSoup(auth_response.text, 'lxml')
        if soup.select_one('#msg1').text == '认证信息无效。':
            logging.warning('学号:' + key + ",密码错误")
            return
    elif auth_response.status_code == 302:
        # 获得ticket认证地址
        url_with_ticket = auth_response.headers['location']
        confirm_response = session.get(url_with_ticket, allow_redirects=True, verify=False)
        if confirm_response.status_code == 200:
            # 进入登录成功界面获得workUrl
            mainPSP = session.get(confirm_response.url + '_s2/students_sy/main.psp', allow_redirects=False,
                                  verify=False)
            workURL = mainPSP.text.split('"workflowDomain": "')[1].split("\"")[0]
            _p = \
                confirm_response.text.split('window.location.href="/portalRedirect.jsp?_p=')[1].split(
                    '"</script>')[
                    0]
            # 获得健康打卡界面信息
            health_response = session.get(workURL + '/default/work/jkd/jkxxtb/jkxxcj.jsp?_p' + _p + '&_l=&_t=')
            infoText = health_response.text.split('showData($(".sui-form").sui().getValue());')[0]
            try:
                empCode = infoText.split('var empCode = \"')[1].split('\"')[0]
            except IndexError:
                empCode = ''
            userOrgId = infoText.split('var userOrgId=\"')[1].split('\"')[0]
            jrstzk = infoText.split('$("div[name=jrstzk]").sui().setValue(\'')[1].split('\'')[0]
            sfjcysqzrq = infoText.split('$("div[name=sfjcysqzrq]").sui().setValue(\'')[1].split('\'')[0]
            sfyqgzdyqryjc = \
                infoText.split('$("div[name=sfyqgzdyqryjc]").sui().setValue(\'')[1].split('\'')[0]
            sfjchwry = infoText.split('$("div[name=sfjchwry]").sui().setValue(\'')[1].split('\'')[0]
            try:
                lzjtgj = infoText.split('$("div[name=lzjtgj]").sui().setValue(\'')[1].split('\'')[0]
            except IndexError:
                lzjtgj = '自驾'
            jgshi = infoText.split('$("div[name=jgshi]").sui().setValue(\'')[1].split('\'')[0]
            sffz = infoText.split('$("div[name=sffz]").sui().setValue(\'')[1].split('\'')[0]
            sflz = infoText.split('$("div[name=sflz]").sui().setValue(\'')[1].split('\'')[0]
            sqbmmc = infoText.split('$("div[name=sqbmmc]").sui().setValue(\'')[1].split('\'')[0]
            jrszd = infoText.split('$("div[name=jrszd]").sui().setValue(\'')[1].split('\'')[0]
            lxdh = infoText.split('$("div[name=lxdh]").sui().setValue(\'')[1].split('\'')[0]
            sqrmc = infoText.split('$("div[name=sqrmc]").sui().setValue(\'')[1].split('\'')[0]
            sqrid = infoText.split('$("div[name=sqrid]").sui().setValue(\'')[1].split('\'')[0]
            xb = infoText.split('$("div[name=xb]").sui().setValue(\'')[1].split('\'')[0]
            sffr = infoText.split('$("div[name=sffr]").sui().setValue(\'')[1].split('\'')[0]
            glqsrq = infoText.split('$("div[name=glqsrq]").sui().setValue(\'')[1].split('\'')[0]
            sfyyqryjc = infoText.split('$("div[name=sfyyqryjc]").sui().setValue(\'')[1].split('\'')[0]
            rysf = infoText.split('$("div[name=rysf]").sui().setValue(\'')[1].split('\'')[0]
            sfzh = infoText.split('$("div[name=sfzh]").sui().setValue(\'')[1].split('\'')[0]
            jrsfjgzgfxdq = \
                infoText.split('$("div[name=jrsfjgzgfxdq]").sui().setValue(\'')[1].split('\'')[0]
            jgshen = infoText.split('$("div[name=jgshen]").sui().setValue(\'')[1].split('\'')[0]
            jrjzdxxdz = infoText.split('$("div[name=jrjzdxxdz]").sui().setValue(\'')[1].split('\'')[0]
            health_data = {
                'entity': {
                    'bz': "",
                    'fhzjbc': "",
                    'fhzjgj': "",
                    'fhzjsj': "",
                    'fztztkdd': "",
                    'gh': empCode,
                    'glqsrq': glqsrq,
                    'jgshen': jgshen,
                    'jgshi': jgshi,
                    'jgzgfxdq': "",
                    'jrjzdxxdz': jrjzdxxdz,
                    'jrsfjgzgfxdq': jrsfjgzgfxdq,
                    'jrstzk': jrstzk,
                    'jrszd': jrszd,
                    'lxdh': lxdh,
                    'lzbc': "",
                    'lzjtgj': lzjtgj,
                    'lzsj': "",
                    'rysf': rysf,
                    'sffr': sffr,
                    'sffz': sffz,
                    'sfjchwry': sfjchwry,
                    'sfjcysqzrq': sfjcysqzrq,
                    'sflz': sflz,
                    'sfyqgzdyqryjc': sfyqgzdyqryjc,
                    'sfyyqryjc': sfyyqryjc,
                    'sfzh': sfzh,
                    'sqbmid': userOrgId,
                    'sqbmmc': sqbmmc,
                    'sqrid': sqrid,
                    'sqrmc': sqrmc,
                    'tbrq': time.strftime("%Y-%m-%d", time.localtime()),
                    'tjsj': time.strftime("%Y-%m-%d %H:%M", time.localtime()),
                    'tw': "36.0",  # 当天体温
                    'xb': xb,
                    'zwtw': "35.9",  # 昨晚体温
                    '_ext': "{}",
                }
            }
            headers = {'Content-Type': 'application/json'}
            jsonData = json.dumps(health_data)
            post_health = session.post(health_response.url.split('/jkxxcj.jsp')[
                                           0] + '/com.sudytech.work.suda.jkxxtb.jktbSave.save.biz.ext?enlink'
                                                '-vpn',
                                       headers=headers, data=jsonData, verify=False)
            if post_health.text == "{\"res\":true}":
                logging.info('学号:' + key + " 打卡成功")
            else:
                logging.warning('学号:' + key + " 打卡失败 {\"res\":false}")
            session.close()


logging.basicConfig(level=logging.INFO)
logging.info('开始任务')
logging.info('连接数据库')
try:
    db = pymysql.connect(host="xxxx", user="xx",
                         password="xxxx", db="xxx", port=3306, charset='utf8')
except Exception as e:
    logging.error('连接数据库失败' + e)
    exit(1)
finally:
    db.close()
scheduler = BlockingScheduler()
scheduler.add_job(main, 'cron', day_of_week='0-6', hour=0, minute=2)
scheduler.start()
