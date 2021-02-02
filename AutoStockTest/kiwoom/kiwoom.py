# test dsa
import os
import logging
import sys
import time
import pandas as pd
from datetime import datetime

import schedule
from PyQt5.QAxContainer import *
from PyQt5.QtCore import *
from config.errorCode import *
from config.kiwoomType import *

NOW_TIME = datetime.today().strftime("%H:%M:%S").strip() # 현재시간 -출력: [09:00:00]
TODAY_DATE = datetime.today().strftime("%Y%m%d").strip() # 오늘날짜 -출력: [20210101]
TIME_SLEEP = 3 # time.sleep(시간)

class Kiwoom(QAxWidget):
    def __init__(self):
        super().__init__() # 부모에 있는 함수를 쓰겠다는 것을 알려줌

        self.logging('debug', "지금부터 주식 자동매매 프로그램을 시작하겠습니다.") # 로그기록

        # eventloop 모음
        self.login_event_loop = None # 로그인 이벤트루프
        self.event_loop = QEventLoop() # 계좌가져오기 이벤트루프
        self.get_stock_info_event = QEventLoop() # 주식일봉차트 이벤트루프
        self.detail_account_info_event_loop = QEventLoop() # 계좌평가잔고내역요청 이벤트루프
        self.get_stock_current_price_event_loop = QEventLoop() # 주식기본정보요청 이벤트루프

        # 스크린번호 모음
        self.screen_start_stop_real = "1000" # 실시간 장시작 및 장마감 스크린번호
        self.screen_my_info = "2000" # 내 계좌번호 스크린번호
        self.screen_date_info = "3000" # 주식일봉차트 스크린번호
        self.screen_real_info = "4000" # 주식기본요청 스크린번호
        self.screen_look_stock = "5001" # look_stock_dict의 스크린번호
        self.screen_swing_stock = "5050" # swing_stock 스크린번호
        self.screen_account_stock = "6001" # 내가 갖고있는 종목 스크린번호

        # 변수 모음
        self.account_num = None # 계좌번호
        self.account_stock_dict = {} # 내계좌 종목
        self.condition_value = {} # 조건식
        self.condition_stock_dict = {} # 조건식에서 포착한 종목
        self.prev_condition_stock_dict = {} # 조건식에서 이탈한 종목
        self.condition_stock_dict_data = [] # 조건식에서 포착한 종목 일봉데이터
        self.look_stock_dict = {} # 언제 포착/이탈 되었는지 기록
        self.swing_stock_dict = {} # 스윙종목(3시)
        self.check_tf = False

        # 계좌 관련 변수
        self.use_money = 0 # 예수금(내가 갖고 있는 돈)
        self.use_money_percent = 0.5 # 예수금 퍼센트(내가 갖고 있는 돈에서 몇퍼센트를 쓸거냐?)

        self.get_ocx_instance()
        self.event_connect()
        self.condition_event_connect()
        self.real_event_connect()

        self.signal_login_commConnect()
        self.get_account_info()
        self.detail_account_info()
        self.detail_mystock_info()

        self.get_condition_name()
        self.get_condition_load()
        # self.send_condition('0', '당일단타(실시간+)', 1, 1)
        # self.send_condition('0', '단타-실시간', 2, 1)
        # self.send_condition('0', '단타', 3, 1)
        # self.send_condition('0', '종목포착', 4, 1)
        
        self.dynamicCall("SetRealReg(QString, QString, QString, QString)", self.screen_start_stop_real, '', RealType.REALTYPE['장시작시간']['장운영구분'], "1")

        for code in self.account_stock_dict.keys():
            screen_num = self.account_stock_dict[code]['스크린번호']
            fids = RealType.REALTYPE['주식체결']['현재가']
            self.dynamicCall("SetRealReg(QString, QString, QString, QString)", screen_num, code, fids, "1")
            print("실시간 등록: %s, fid번호: %s, 스크린번호: %s" % (code, fids, screen_num))


        # for code in self.condition_stock_dict:
        #     self.get_stock_current_price(code)

        # self.look_stock_dict = {'122350': {'이벤트': 'D', '포착시간': '15:18:06', '종목명': '삼기', '스크린번호': '5001', '포착가': 5750, '현재가': 5800},
        #                         '086980': {'이벤트': 'I', '포착시간': '15:18:42', '종목명': '쇼박스', '스크린번호': '5001', '포착가': 4505, '현재가': 4510},
        #                         '009470': {'이벤트': 'I', '포착시간': '15:19:54', '종목명': '삼화전기', '스크린번호': '5001', '포착가': 24550, '현재가': 24500}}
        #
        # df = pd.DataFrame(self.look_stock_dict)
        # df.to_csv('./file/data_{:%Y%m%d}.csv'.format(datetime.now()), encoding='cp949')
        # print("df")


    def realdata_slot(self, sCode, sRealType, sRealData): # 실시간으로 데이터 받아옴
        if sRealType == "장시작시간":
            fid = RealType.REALTYPE[sRealType]['장운영구분']
            value = self.dynamicCall("GetCommRealData(QString, int)", sCode, fid)

            if value == "0":
                print("장 시작 전")
            elif value == "2":
                print("장 종료 전")
                if self.check_tf == False:
                    self.check_tf == True
                    for code in self.account_stock_dict.keys():
                        self.dynamicCall("SetRealRemove(QString, QString)", self.account_stock_dict[code]['스크린번호'], code)

                    self.send_condition('0', '종목포착test', 5, 0)

                    self.get_stock_info_start()  # 일봉차트가져오기


            elif value == "3":
                print("9시 장 시작")
            elif value == "4":
                print("3시 30분 장 종료")
                self.logging('debug', '장 종료 후 프로그램이 정상적으로 종료되었습니다.')
                sys.exit()

        elif sRealType == "주식체결":
            current_price = abs(int(self.dynamicCall("GetCommRealData(QString, int)", sCode, RealType.REALTYPE[sRealType]['현재가'])))
            trade_count = abs(int(self.dynamicCall("GetCommRealData(QString, int)", sCode, RealType.REALTYPE[sRealType]['누적거래량'])))
            trade_percent = abs(float(self.dynamicCall("GetCommRealData(QString, int)", sCode, RealType.REALTYPE[sRealType]['전일거래량대비'])))

            get_percent = ((current_price / self.account_stock_dict[sCode]['매입가']) - 1) * 100 # ((현재 주식 가격 / 매수 때 주식가격) - 1) * 100 ---수익률---


            if get_percent > 2 and get_percent < 10: # 2%일시 매도 (3%)
                print("[%s] 얼마이득? %s / 몇퍼이득? %s" % (sCode, current_price-self.account_stock_dict[sCode]['매입가'], get_percent))
                self.send_order("신규매도", self.account_stock_dict[sCode]['스크린번호'], self.account_num, 2, sCode,
                                self.account_stock_dict[sCode]['보유수량'], current_price, RealType.SENDTYPE['거래구분']['지정가'], "")
                self.dynamicCall("SetRealRemove(QString, QString)", self.account_stock_dict[sCode]['스크린번호'], sCode)

            elif get_percent < -3: # -3%일시 매도 (-4%)
                print("[%s] 얼마손해? %s / 몇퍼손해? %s" % (sCode, current_price-self.account_stock_dict[sCode]['매입가'], get_percent))
                self.send_order("신규매도", self.account_stock_dict[sCode]['스크린번호'], self.account_num, 2, sCode,
                                 self.account_stock_dict[sCode]['보유수량'], current_price, RealType.SENDTYPE['거래구분']['지정가'], "")
                self.dynamicCall("SetRealRemove(QString, QString)", self.account_stock_dict[sCode]['스크린번호'], sCode)


    def send_order(self, sRQName, sScreenNo, sAccNo, nOrderType, sCode, nQty, nPrice, sHogaGb, sOrgOrderNo): # 매수 및 매도주문 함수
        '''
        SendOrder(BSTR sRQName, // 사용자 구분명
        BSTR sScreenNo, // 스크린번호
        BSTR sAccNo, // 계좌번호 10자리
        LONG nOrderType, // 주문유형 1:신규매수, 2:신규매도 3:매수취소, 4:매도취소, 5:매수정정, 6:매도정정
        BSTR sCode, // 종목코드
        LONG nQty, // 주문수량
        LONG nPrice, // 주문가격
        BSTR sHogaGb, // 거래구분(혹은 호가구분)
        BSTR sOrgOrderNo // 원주문번호
        '''
        self.dynamicCall("SendOrder(QString, QString, QString, int, QString, int, int, QString, QString",
                         [sRQName, sScreenNo, sAccNo, nOrderType, sCode, nQty, nPrice, sHogaGb, sOrgOrderNo])

        print('[%s] %s' % (sCode, sRQName))
        if sRQName == '신규매수':
            f = open('./file/{:%Y%m%d}_buy_stock.txt'.format(datetime.now()), "a", encoding="cp949")
            f.write("%s\t%s\t%s\t%s\tbuy: %s\n" % (TODAY_DATE, sRQName, sCode, self.swing_stock_dict[sCode]['종목명'], nPrice))
            f.close()
        else:
            f = open('./file/{:%Y%m%d}_sell_stock.txt'.format(datetime.now()), "a", encoding="cp949")
            f.write("%s\t%s\t%s\t%s\tbuy: %s\tsell: %s\tprofit: %s\n" % (TODAY_DATE, sRQName, sCode, self.account_stock_dict[sCode]['종목명'], self.account_stock_dict[sCode]['매입가'], nPrice, nPrice-self.account_stock_dict[sCode]['매입가']))
            f.close()

        # self.logging('info', "%s;%s;%s;%s;%s;%s\n" % (sRQName, sCode, self.account_stock_dict[sCode]['종목명'], self.account_stock_dict[sCode]['매입가'], nPrice, get_percent))


    def get_stock_info_start(self): # 코드 정보 가져오기
        codelist = self.condition_stock_dict.keys()
        print(codelist)

        for idx, code in enumerate(codelist):
            self.dynamicCall("DisconnectRealData(QString)", self.screen_date_info)  # A요청 후 B를 요청하기 위해 A 데이터 끊고 B요청(스크린 끊기)
            print("[%s / %s] 코스닥 종목 중 [CODE : %s]" % (idx+1, len(codelist), code))
            self.get_stock_info(code=code)

        print("결과[%s개]: %s" % (len(self.swing_stock_dict), self.swing_stock_dict))

        # for code in self.swing_stock_dict.keys():


    ### 함 수 영 역 ###
    def get_ocx_instance(self): # 응용프로그램(키움OpenAPI)들을 제어가능하게 만들어주는 함수
        self.setControl("KHOPENAPI.KHOpenAPICtrl.1") # KHOPENAPI.KHOpenAPICtrl.1 라는 레지스트리 컨트롤


    def event_connect(self): # 로그인 요청
        self.OnEventConnect.connect(self.login_slot) # 로그인 이벤트함수(키움OpenAPI)
        self.OnReceiveTrData.connect(self.trData_slot) # Tr데이터 사용하기 위한 슬롯만들기(trData_slot에 받음)
        self.OnReceiveMsg.connect(self.msg_slot)


    def condition_event_connect(self): # 조건식 검색 요청
        self.OnReceiveConditionVer.connect(self.receiveConditionVer)
        self.OnReceiveTrCondition.connect(self.receiveTrCondition)
        # self.OnReceiveRealCondition.connect(self.receiveRealCondition)


    def real_event_connect(self):  # 실시간 데이터 요청
        self.OnReceiveRealData.connect(self.realdata_slot)


    def login_slot(self, errCode): # errCode반환 (0일경우 로그인성공)
        self.login_event_loop.exit()  # 로그인성공시
        if errCode != 0:
            print(errors(errCode))  # errorCode 출력
            self.logging('error', "접속불가> 로그인실패[%s]" % errors(errCode))
            return
        self.logging('debug', "---접속완료---")


    def signal_login_commConnect(self): # 로그인 시도
        # dynamicCall (데이터를 다른 서버에 전송해주는 pyqt5 함수)
        self.dynamicCall("CommConnect()") # CommConnect() 함수 사용을 위한 데이터 전송 (로그인시도)
        self.login_event_loop = QEventLoop() # 로그인이 될때까지

        self.login_event_loop.exec_()


    def get_account_info(self): # 계좌번호 가져오기
        account_list = self.dynamicCall("GetLogininfo(String)", "ACCNO") # 계좌번호 가져옴 데이터 전송
        self.account_num = account_list.split(';')[0] #  예) "3040525910;567890;" ->  '3040525910' 가져옴


    def detail_account_info(self):
        # 예수금상세현황요청 데이터 (계좌번호, 비밀번호, 비밀번호입력매채구분, 조회구분)
        self.dynamicCall("SetInputValue(String, String)", "계좌번호", self.account_num)
        self.dynamicCall("SetInputValue(String, String)", "비밀번호", "0000")
        self.dynamicCall("SetInputValue(String, String)", "비밀번호입력매채구분", "00")
        self.dynamicCall("SetInputValue(String, String)", "조회구분", "2")
        self.dynamicCall("CommRqData(QString, QString, int, QString)", "예수금상세현황요청", "opw00001", "0", self.screen_my_info)

        self.event_loop.exec_()


    def detail_mystock_info(self, sPrevNext="0"): # 계좌평가잔고내역  opw00018
        self.dynamicCall("SetInputValue(String, String)", "계좌번호", self.account_num)
        self.dynamicCall("SetInputValue(String, String)", "비밀번호", "0000")
        self.dynamicCall("SetInputValue(String, String)", "비밀번호입력매채구분", "00")
        self.dynamicCall("SetInputValue(String, String)", "조회구분", "2")
        self.dynamicCall("CommRqData(QString, QString, int, QString)", "계좌평가잔고내역요청", "opw00018", sPrevNext, self.screen_my_info)

        self.detail_account_info_event_loop.exec_()


    def get_stock_info(self, code, date=None, sPrevNext="0"): # 주식일봉차트조회  opt10081
        time.sleep(TIME_SLEEP)
        self.dynamicCall("SetInputValue(QString, QString)", "종목코드", code)
        self.dynamicCall("SetInputValue(QString, QString)", "수정주가구분", "1")
        if date != None:
            self.dynamicCall("SetInputValue(QString, QString)", "기준일자", date)
        self.dynamicCall("CommRqData(QString, QString, int, QString)", "주식일봉차트조회", "opt10081", sPrevNext, self.screen_date_info)

        self.get_stock_info_event.exec_()


    def receiveConditionVer(self, receive, msg): # 조건검색식 가져오기
        print("receiveConditionVer")
        '''
        :param receive: int - 응답결과(1: 성공, 나머지 실패)
        :param msg: string - 메세지
        '''
        if not receive:
            print("오류: %s" % msg)
            return
        print("조건식 개수: %s" % len(self.condition_value))
        for key in self.condition_value.keys():
            print("조건식: %s : %s " % (key, self.condition_value[key]))

        self.conditionLoop.exit()

    def receiveTrCondition(self, sScrNo, codes, conditionName, conditionIndex, inquiry): # 내 조건검색식에서 포착된 종목이름 가져오기
        print("receiveTrCondition")
        # print(sScrNo, codes, conditionName, conditionIndex, inquiry) -> [0 008250; 단타-실시간 2 0]
        """
        (1회성, 실시간) 종목 조건검색 요청시 발생되는 이벤트
        :param sScrNo: string
        :param codes: string - 종목코드 목록(각 종목은 ;으로 구분됨)
        :param conditionName: string - 조건식 이름
        :param conditionIndex: int - 조건식 인덱스
        :param inquiry: int - 조회구분(0: 남은데이터 없음, 2: 남은데이터 있음)
        """
        if codes == "":
            print("[%s] 검색식에 포착된 종목 없음" % conditionName)
            return

        codeList = codes.split(';')
        del codeList[-1] # 공백 없애줌
        print("종목개수: %s개" % len(codeList))

        for code in codeList:
            code_name = self.get_code_name(code)
            if code in self.condition_stock_dict:  # 만약 코드가 딕셔너리에 있으면 패스 / 없으면 만들어줌 (종목번호)
                pass
            else:
                self.condition_stock_dict.update({code: {}})

            self.condition_stock_dict[code].update({"종목명": code_name})

        print("condition %s" % self.condition_stock_dict)
        self.conditionLoop.exit()


    def send_condition(self, sScrNo, conditionName, conditionIdx, isRealTime): # 종목 조건 검색 요청
        print("send_condition")
        '''
        :param sScrNo: 스크린 번호
        :param conditionName: 조건검색식 이름
        :param conditionIdx: 조건검색식 인덱스
        :param isRealTime: 조건검색 조회구분(0: 1회성 구분, 1: 실시간 조회)
        :return:
        '''
        isRequest = self.dynamicCall("SendCondition(QString, QString, int, int", sScrNo, conditionName, conditionIdx, isRealTime)
        if not isRequest:
            print("send_condition() 조건 검색실패")

        self.conditionLoop = QEventLoop()
        self.conditionLoop.exec_()


    def get_condition_load(self): # 조건식 목록 요청 함수
        print("get_condition_load")
        isLoad = self.dynamicCall("GetConditionLoad()") # isLoad가 0일경우 실패, 1일경우 불러오기 성공

        if isLoad == 0:
            print("GetConditionLoad() 요청 실패")

        self.conditionLoop = QEventLoop()
        self.conditionLoop.exec_()


    def get_condition_name(self): #  조건식 이름 가져오는 함수
        print("get_condition_name")
        data = self.dynamicCall("GetConditionNameList()")

        if data == "":
            print("GetConditionNameList() 요청실패")

        conditionList = data.split(';')
        del conditionList[-1]

        for condition in conditionList: # 조건식 검색
            condition_idx, condition_name = condition.split('^')
            self.condition_value[int(condition_idx)] = condition_name
            # print ['000^단기1', '001^당일단타(실시간+)', '002^단타-실시간'] -> ['단기1', '당일단타(실시간+)', '단타-실시간']

        print("검색식: %s" % self.condition_value)


    ### DATA_SLOT 부분 ###
    def trData_slot(self, sScrNo, sRQName, sTrCode, sRecordName, sPrevNext):
        '''
        tr 요청을 받는 구역 (슬롯)
        :param sScrNo: 스크린번호
        :param sRQName: 내가 요청했을때 지은 이름
        :param sTrCode: 요청id, tr코드
        :param sRecordName: 사용 안함
        :param sPrevNext: 다음 페이지가 있는지
        :return:
        '''
        if sRQName == "예수금상세현황요청": # opw00001
            print('-*예수금상세현황요청란*-')
            deposit = self.dynamicCall("GetCommData(String, String, int, String)", sTrCode, sRQName, 0, "예수금")

            self.use_money = int(deposit)

            print('예수금: %s' % int(deposit))
            print('주문가능금액: %s' % int(self.use_money))

            print('*예수금상세현황요청란*')
            self.event_loop.exit()

        elif sRQName == "계좌평가잔고내역요청":
            total_buy_money = self.dynamicCall("GetCommData(String, String, int, String)", sTrCode, sRQName, 0, "총매입금액")
            total_profit_loss_rate = self.dynamicCall("GetCommData(String, String, int, String)", sTrCode, sRQName, 0, "총수익률(%)")
            rows = self.dynamicCall("GetRepeatCnt(QString, QString)", sTrCode, sRQName) # 보유종목이 몇개인지 카운트

            for i in range(rows):
                code = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "종목번호")
                code_name = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "종목명")
                stock_quantity = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i,"보유수량")
                buy_price = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "매입가")
                learn_rate = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i,"수익률(%)")
                current_price = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i,"현재가")
                total_chegual_price = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName,i, "매입금액")
                possible_quantity = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i,"매매가능수량")
                code = code.strip()[1:]  # " A3333  " 양쪽 공백 지워주고(strip), 첫번째 문자 지워줌 = "3333"
                code_name = code_name.strip()
                stock_quantity = int(stock_quantity.strip())
                buy_price = int(buy_price.strip())
                learn_rate = float(learn_rate.strip())
                current_price = int(current_price.strip())
                total_chegual_price = int(total_chegual_price.strip())
                possible_quantity = int(possible_quantity.strip())

                if code not in self.account_stock_dict:
                    self.account_stock_dict.update({code: {}})

                self.account_stock_dict[code].update({"종목명": code_name})
                self.account_stock_dict[code].update({"보유수량": stock_quantity})
                self.account_stock_dict[code].update({"매입가": buy_price})
                self.account_stock_dict[code].update({"수익률(%)": learn_rate})
                self.account_stock_dict[code].update({"현재가": current_price})
                self.account_stock_dict[code].update({"매입금액": total_chegual_price})
                self.account_stock_dict[code].update({"매매가능수량": possible_quantity})
                self.account_stock_dict[code].update({"스크린번호": self.screen_account_stock})

            print("갖고있는종목[%s]: [%s] [%s]" % (rows, self.account_stock_dict.keys(), self.account_stock_dict.values()))

            if sPrevNext == "2": # 만약 다음페이지가 있으면 2번째 페이지로 가고, 없다면 연결끊음
                self.detail_mystock_info(sPrevNext="2")
            else:
                self.detail_account_info_event_loop.exit()

        elif sRQName == "주식일봉차트조회":
            print("---주식일봉차트조회 실행---")
            code = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "종목코드")
            code = code.strip()
            cnt = self.dynamicCall("GetRepeatCnt(QString, QString)", sTrCode, sRQName)

            for i in range(cnt):
                data = []
                date = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "일자").strip()
                current_price = int(self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "현재가").strip())
                start_price = int(self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "시가").strip())
                high_price = int(self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "고가").strip())
                low_price = int(self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "저가").strip())
                trade_cnt = int(self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "거래량").strip())
                trading_value = int(self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "거래대금").strip())

                data.append(date)
                data.append(code)
                data.append(current_price)
                data.append(start_price)
                data.append(high_price)
                data.append(low_price)
                data.append(trade_cnt)
                data.append(trading_value)

                self.condition_stock_dict_data.append(data.copy())

            # total_20_price = 0 # 20일선 구하는거
            # for value in self.condition_stock_dict_data[:20]:
            #     total_20_price += int(value[2])
            # total_20_price = total_20_price / 20
            # print(total_20_price)

            if self.condition_stock_dict_data[0][2] >= self.condition_stock_dict_data[0][3]: # 오늘 양봉일경우
                print("[%s] 는 양봉이면서" % code)
                if self.condition_stock_dict_data[0][5] < self.condition_stock_dict_data[0][3]: # 밑으로 꼬리가 있을경우
                    print("[%s] 밑으로 꼬리가 있어" % code)
                    self.swing_stock_dict.update({code:{}})
                    self.swing_stock_dict[code].update({"종목명": self.get_code_name(code)})
                    self.swing_stock_dict[code].update({"현재가": self.condition_stock_dict_data[0][2]})
                    self.swing_stock_dict[code].update({"스크린번호": self.screen_swing_stock})

                    self.send_order("신규매수", self.swing_stock_dict[code]['스크린번호'], self.account_num, 1, code,
                                    1, self.swing_stock_dict[code]['현재가'], RealType.SENDTYPE['거래구분']['지정가'], "")

            else: # 오늘 음봉일경우
                print("[%s] 는 음봉" % code)

            self.condition_stock_dict_data.clear()
            self.get_stock_info_event.exit()


    ### 로그 출력 ###
    def logging(self, level, msg):
        # 로그 생성
        logger = logging.getLogger('AUTO_STOCK_LOG')
        # 로그의 출력 기준 설정
        if level == 'info':
            logger.setLevel(logging.INFO)
        elif level == 'debug':
            logger.setLevel(logging.DEBUG)
        elif level == 'critical':
            logger.setLevel(logging.CRITICAL)
        elif level == 'warning':
            logger.setLevel(logging.WARNING)
        elif level == 'error':
            logger.setLevel(logging.ERROR)

        # log 출력 형식
        formatter = logging.Formatter('[%(asctime)s][%(levelname)s]> %(message)s')
        # log 출력
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        # log를 파일에 출력
        file_handler = logging.FileHandler(filename='./log/autolog_{:%Y%m%d}.log'.format(datetime.now()), encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        if level == 'info':
            logger.info('%s' % msg)
        elif level == 'debug':
            logger.debug('%s' % msg)
        elif level == 'critical':
            logger.critical('%s' % msg)
        elif level == 'warning':
            logger.warning('%s' % msg)
        elif level == 'error':
            logger.error('%s' % msg)

        logger.removeHandler(stream_handler)
        logger.removeHandler(file_handler)


    #############
    def msg_slot(self, sScrNo, sRQName, sTrCode, msg): # 서버 송수신 메세지 출력
        print("스크린: %s, 요청이름: %s, tr코드: %s --- %s" % (sScrNo, sRQName, sTrCode,msg))

    ### code로 가져올수 있는 값들 ###
    def get_code_name(self, code):  # 종목코드에 해당하는 종목명 전달
        result = self.dynamicCall("GetMasterCodeName(QString)", code)
        return result

    def get_construction(self, code):  # 정상, 투자주의, 투자경고, 투자위험, 투자주의환기종목 전달
        result = self.dynamicCall("GetMasterConstruction(QString)", code)
        return result

    def get_stock_state(self, code):  # 증거금 비율, 거래정지, 관리종목, 감리종목, 투자융의종목, 담보대출, 액면분할, 신용가능 여부 전달
        result = self.dynamicCall("GetMasterStockState(QString)", code)
        return result

    def get_last_price(self, code):  # 입력한 종목의 전일가 전달
        result = self.dynamicCall("GetMasterLastPrice(QString)", code)
        return result


    ### 필요없는 식 ###
    '''
    def receiveRealCondition(self, code, event, conditionName, conditionIndex): # 조건검색식에서 편입 및 이탈종목 가져오기
            print("receiveRealCondition")
            """
            실시간 종목 조건검색 요청시 발생되는 이벤트
            :param code: string - 종목코드
            :param event: string - 이벤트종류("I": 종목편입, "D": 종목이탈)
            :param conditionName: string - 조건식 이름
            :param conditionIndex: string - 조건식 인덱스(여기서만 인덱스가 string 타입으로 전달됨)
            """
            code_name = self.get_code_name(code)

            if(event == "I"):
                if code not in self.condition_stock_dict:  # 만약 코드가 딕셔너리에 있으면 패스 / 없으면 만들어줌 (종목번호)
                    self.condition_stock_dict.update({code: {}})

                self.condition_stock_dict[code].update({"종목명": code_name})
                self.condition_stock_dict[code].update({"스크린번호": self.screen_look_stock})

                if code in self.prev_condition_stock_dict:
                    del self.prev_condition_stock_dict[code]

                print("이벤트: [ %s-%s ] ++종목편입++" % (code, code_name))

            else:
                if code not in self.prev_condition_stock_dict:  # 만약 코드가 딕셔너리에 있으면 패스 / 없으면 만들어줌 (종목번호)
                    self.prev_condition_stock_dict.update({code: {}})

                self.prev_condition_stock_dict[code].update({"종목명": code_name})

                del self.condition_stock_dict[code]
                print("이벤트: [ %s-%s ] --종목이탈--" % (code, code_name))

            if len(self.condition_stock_dict) % 50 == 0:
                self.screen_look_stock = str(int(self.screen_look_stock) + 1)

            print("실시간 종목[%s개]: %s" % (len(self.condition_stock_dict), self.condition_stock_dict))
            print("실시간 이탈종목[%s개]: %s" % (len(self.prev_condition_stock_dict), self.prev_condition_stock_dict))
            
    def getstock_current_price(self, code): # 주식기본정보요청 __opt10001___
        time.sleep(TIME_SLEEP)
        self.dynamicCall("SetInputValue(String, String)", "종목코드", code)
        self.dynamicCall("CommRqData(String, String, int, String)", "주식기본정보요청", "opt10001", 0, self.screen_real_info)

        self.get_stock_current_price_event_loop.exec_()

    
    #trData_slot에 들어감
    elif sRQName == "주식기본정보요청":
    print("--주식기본정보요청--")
    data = {}
    code = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "종목코드").strip()
    code_name = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "종목명").strip()
    current_price = int(
        self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "현재가").strip())

    if code in self.condition_stock_dict.keys():
        self.condition_stock_dict[code].update({"현재가": current_price})
        data.update({"편입종목": "+"})
    elif code in self.prev_condition_stock_dict.keys():
        self.prev_condition_stock_dict[code].update({"현재가": current_price})
        data.update({"이탈종목": "-"})

    self.look_stock_dict.update({code: {}})

    data.update({"시간": NOW_TIME})
    data.update({"종목명": code_name})
    data.update({"포착가": current_price})

    self.look_stock_dict[code].update(data.copy())

    print("look : %s " % self.look_stock_dict)

    self.get_stock_current_price_event_loop.exit()
'''