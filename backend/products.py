from flask import Flask, jsonify, request, abort, Blueprint
from flask.ext.mysql import MySQL
import json, codecs
import boto3
from werkzeug.utils import secure_filename
import datetime
import utils

config = json.load(codecs.open('config.json', encoding='utf-8'))
app = Flask(__name__)
mysql = MySQL()
client = boto3.client('s3')

app.config['MYSQL_DATABASE_USER'] = config['db_user']
app.config['MYSQL_DATABASE_PASSWORD'] = config['db_passwd']
app.config['MYSQL_DATABASE_DB'] = config['db_db']
app.config['MYSQL_DATABASE_HOST'] = config['db_host']
mysql.init_app(app)

products = Blueprint('products', __name__)

#author: Yang
#Deprecated
@products.route('/products', methods=['POST'])
def get_all_products():
	productsList = []

	db = mysql.connect()
	cursor = db.cursor()
	cursor.execute("SELECT * FROM Product ORDER BY postTime;")
	if cursor.rowcount > 0:
		productList = cursor.fetchall()
		for pRow in productList:
			userId = pRow[0]
			pid = pRow[1]
			pName = pRow[2]
			pPrice = str(pRow[3])
			pInfo = pRow[4]
			postTime = pRow[5]
			usedTime = pRow[6]
			isSold = pRow[7]
			imageCur = db.cursor()
			imageCur.execute("SELECT imageURL FROM ProductImage WHERE pid = '%d';"%pid)
			imageList = []
			if imageCur.rowcount > 0:
				imageR = imageCur.fetchall()
				for i in imageR:
					imageList.append(i[0])
			userCur = db.cursor()
			userCur.execute("SELECT nickname FROM UserInfo WHERE userId = '%d';"%userId)
			if userCur.rowcount >0:
				nickname = userCur.fetchall()[0][0]
			currentProduct = {}
			currentProduct['nickname'] = nickname
			currentProduct['userId'] = userId
			currentProduct['pid'] = pid
			currentProduct['pName'] = pName
			currentProduct['pPrice'] = pPrice
			currentProduct['pInfo'] = pInfo
			currentProduct['postTime'] = postTime
			currentProduct['usedTime'] = usedTime
			currentProduct['images'] = imageList
			currentProduct['isSold'] = isSold
			productsList.append(currentProduct)
	db.close()
	return jsonify({'products':productsList})


#author: Wen
#Deprecated
@products.route('/products/tags', methods=['POST'])
def get_tag_pid():
	
	if not request.json or not 'tag' in request.json:
		abort(400, '{"message":"Input parameter incorrect or missing"}')
	tag = request.json['tag']
	
	db = mysql.connect()
	cursor = db.cursor()
	tag = tag.replace('_',' ')
	cursor.execute("SELECT tid FROM Tag WHERE tag = '%s';"%tag)
	pidList = []
	if cursor.rowcount == 1:
		tid = cursor.fetchall()[0]
		pidCur = db.cursor()
		pidCur.execute("SELECT pid FROM ProductTag WHERE tid = '%d';"%tid)
		if pidCur.rowcount > 0:
			pidList = [item[0] for item in pidCur.fetchall()]
		db.close()
		return jsonify({'pids':pidList})
	else:
		db.close()
		abort(400,"Incorrect Tag")

#author: Yichen, Wen
#authentication
@products.route('/products/details', methods=['POST'])
def get_tag_details():
	if not request.json or not 'userId' in request.json or not 'pid' in request.json or not 'token' in request.json:
		abort(400, '{"message":"Input parameter incorrect or missing"}')
	userId = request.json['userId']
	pid = request.json['pid']
	token = request.json['token']
	if not utils.authenticateToken(userId, token):
		abort(401)

	tagList = []
	db = mysql.connect()
	cursor = db.cursor()

	cursor.execute("SELECT tid FROM ProductTag WHERE pid = '%s';"%pid)
	if cursor.rowcount > 0:
		tidList = cursor.fetchall()
		for tid in tidList:
			tidCur = db.cursor()
			tidCur.execute("SELECT tag from Tag WHERE tid = '%s';"%tid)
			if tidCur.rowcount > 0:
				tagList = tidCur.fetchall()[0]

			else:
				continue
	favCur = db.cursor()
	favCur.execute("SELECT * FROM UserLike WHERE userId = %s AND pid = %s",[userId, pid])
	if favCur.rowcount == 1:
		isFavorite = True
	else: 
		isFavorite = False
	db.close()
	return jsonify({'tagList':tagList, 'isFavorite':isFavorite})


#author: Wen
#authentication
@products.route('/products/add/images', methods=['POST'])
def product_uploader():
	if not request.files or not request.json or not 'files' in request.files or not 'pid' in request.json or not 'userId' in request.json or not 'token' in request.json:
		abort(400, '{"message":"Input parameter incorrect or missing"}')

	fileList = request.files.getlist('files')
	if len(fileList) == 0:
		abort(400)

	pid = request.json['pid']
	userId = request.json['userId']
	token = request.json['token']
	if not utils.authenticateToken(userId, token):
		abort(401)

	db = mysql.connect()
	cursor = db.cursor()
	addressList = []
	for file in fileList:
		filename = secure_filename(file.filename)
		client.upload_fileobj(file, 'gtthriftshopproducts', pid + "/" + filename)
		imageURL = "https://s3-us-west-2.amazonaws.com/gtthriftshopproducts/" + pid + "/" + filename
		addressList.append(imageURL)
		try:
			cursor.execute("INSERT INTO ProductImage(pid,imageURL) values(%s,%s)", [pid,imageURL])
		except:
			db.rollback()
			db.close()
			abort(400, '{"message":"upload unsuccessful"}')
	db.commit()
	db.close()
	return jsonify({'photoUrls':addressList})


#author: Yichen, Wen
#authentication
@products.route('/products/add/allInfo', methods=['POST'])
def add_product():
	if not request.json or not 'userId' in request.json or not 'pName' in request.json or not 'pPrice' in request.json or not 'pInfo' in request.json or not 'tag' in request.json or not 'usedTime' in request.json or not 'token' in request.json: 
		abort(400, '{"message":"Input parameter incorrect or missing"}')
	userId = request.json['userId']
	pName = request.json['pName']
	pPrice = float(request.json['pPrice'])
	pInfo = request.json['pInfo']
	usedTime = request.json['usedTime']
	tag = request.json['tag']
	token = request.json['token']
	if not utils.authenticateToken(userId, token):
		abort(401)

	isSold = 0
	postTime = datetime.datetime.now()
	db = mysql.connect()
	cursor = db.cursor()
	cursor.execute("SELECT tid FROM Tag WHERE tag = '%s'"%tag)
	tid = [item[0] for item in cursor.fetchall()]
	try:
		cursor.execute("INSERT INTO Product(userId,pName,pPrice,pInfo,postTime,usedTime,isSold) values (%s,%s,%s,%s,%s,%s,%s)",[userId,pName,pPrice,pInfo,postTime,usedTime,isSold])
		pid = cursor.lastrowid
		cursor.execute("INSERT INTO ProductTag(pid,tid) values(%s,%s)",[pid,tid])
		db.commit()
		db.close()
		return jsonify({'pid':pid})
	except:
		db.rollback()
		db.close()
		abort(400, '{"message":"Product info added unsuccessful"}')


#author: Yichen, Wen
#authentication
@products.route('/products/info/update', methods=['POST'])
def update_product_info():
	if not request.json or not 'pid' in request.json or not 'pName' in request.json or not 'pPrice' in request.json or not 'pInfo' in request.json or not 'tag' in request.json or not 'usedTime' in request.json or not 'userId' in request.json or not 'token' in request.json: 
		abort(400, '{"message":"Input parameter incorrect or missing"}')
	pid = request.json['pid']
	pName = request.json['pName']
	pPrice = float(request.json['pPrice'])
	pInfo = request.json['pInfo']
	tag = request.json['tag']
	usedTime = request.json['usedTime']
	userId = request.json['userId']
	token = request.json['token']
	if not utils.authenticateToken(userId, token):
		abort(401)

	db = mysql.connect()
	cursor = db.cursor()
	cursor.execute("SELECT tid FROM Tag WHERE tag = '%s'"%tag)
	tid = [item[0] for item in cursor.fetchall()]
	cursor.execute("SELECT * FROM Product WHERE pid = %s AND isSold = %s",[pid, 0])
	if cursor.rowcount == 1:
		cursor.execute("UPDATE Product SET pName = %s, pPrice = %s, pInfo = %s, usedTime = %s WHERE pid = %s",[pName,pPrice,pInfo,usedTime,pid])
		cursor.execute("UPDATE ProductTag SET tid = %s WHERE pid = %s",[tid, pid])
		db.commit()
		db.close()
		return("Success") 
	else:
		db.rollback()
		db.close()
		abort(400, 'fail')


#author: Yichen, Wen
#authentication
@products.route('/products/update/isSold', methods=['POST'])
def update_isSold():
	if not request.json or not 'userId' in request.json or not 'pid' in request.json or not 'token' in request.json:
		abort(400, '{"message":"Input parameter incorrect or missing"}')
	userId = request.json['userId']
	pid = request.json['pid']
	token = request.json['token']
	if not utils.authenticateToken(userId, token):
		abort(401)

	isSold = 1
	postTime = datetime.datetime.now()
	db = mysql.connect()
	cursor = db.cursor()
	cursor.execute("SELECT isSold FROM Product WHERE pid = %s AND isSold = %s",[pid, 0])
	if cursor.rowcount == 1:
		try:
			cursor.execute("UPDATE Product SET isSold = '%s' WHERE pid = %s", [isSold,pid])
			cursor.execute("INSERT INTO Transaction(pid,buyerId,time) values (%s,%s,%s)",[pid, userId, postTime])
			newTranId = cursor.lastrowid
			db.commit()
			db.close()
			return("Success") 
		except:
			db.rollback()
			db.close()
			abort(400, '{"message":"product sold is unsuccessful"}')
	else:
		db.close()
		abort(400,"Product not found or item has been sold already")


#author: Yang, Wen
#authentication
@products.route('/products/add/interest', methods=['POST'])
def add_interest():
	if not request.json or not 'userId' in request.json or not 'pid' in request.json or not 'token' in request.json:
		abort(400, '{"message":"Input parameter incorrect or missing"}')
	userId = request.json['userId']
	pid = request.json['pid']
	token = request.json['token']
	if not utils.authenticateToken(userId, token):
		abort(401)

	db = mysql.connect()
	cursor = db.cursor()
	try:
		cursor.execute("INSERT INTO InterestList(pid,interestUId) values (%s,%s)",[pid,userId])
		db.commit()
		db.close()
		return("success")
	except:
		db.rollback()
		db.close()
		abort(400, '{"message":"add interest user unsuccessful"}')

#author: Yichen, Wen
#authentication
@products.route('/products/getInterest', methods=['POST'])
def get_interest():
	if not request.json or not 'userId' in request.json or not 'token' in request.json:
		abort(400, '{"message":"Input parameter incorrect or missing"}')
	userId = request.json['userId']
	token = request.json['token']
	if not utils.authenticateToken(userId, token):
		abort(401)

	result = []
	finalList = []
	db = mysql.connect()
	cursor = db.cursor()
	
	cursor.execute("SELECT pid FROM Product WHERE userId = '%s';"%userId)
	if cursor.rowcount > 0:
		pidList1 = [item[0] for item in cursor.fetchall()]
		for pid in pidList1:
			p1Cur = db.cursor()
			p1Cur.execute("SELECT interestUId FROM InterestList WHERE pid = '%s';"%pid)
			result = [item[0] for item in p1Cur.fetchall()]
	
	cursor.execute("SELECT pid FROM InterestList WHERE interestUId = '%s';"%userId)
	if cursor.rowcount > 0:
		pidList2 = cursor.fetchall()
		for pid in pidList2:
			p2Cur = db.cursor()
			p2Cur.execute("SELECT userId from Product WHERE pid = '%s';"%pid)
			userRow = p2Cur.fetchall()[0]
			userList = int(userRow[0])
			result.append(userList)
	result = sorted(set(result))

	for r in result:
		rCur = db.cursor()
		rCur.execute("SELECT nickname, userId, avatarURL FROM UserInfo where userId = '%s';"%r)
		rList = rCur.fetchall()[0]
		resultList = {}
		resultList['username'] = rList[0]
		resultList['userId'] = rList[1]
		resultList['avatarURL'] = rList[2]
		finalList.append(resultList)
	db.close()
	return jsonify({'Interest':finalList})


#author: Wen
#authentication
@products.route('/products/getAllPost', methods=['POST'])
def get_all_post():
	if not request.json or not 'userId' in request.json or not 'token' in request.json:
		abort(400, '{"message":"Input parameter incorrect or missing"}')
	userId = request.json['userId']
	token = request.json['token']
	if not utils.authenticateToken(userId, token):
		abort(401)

	db = mysql.connect()
	cursor = db.cursor()
	cursor.execute("SELECT pid FROM Product WHERE userId = '%s';"%userId) 
	if cursor.rowcount > 0:
		pidList = [item[0] for item in cursor.fetchall()]
		db.close()
		return jsonify({'PostPids':pidList})
	else :
		db.close()
		abort(400,"Unknown userId")


#author: Wen
#authentication
@products.route('/products/interest', methods=['POST'])
def get_product_interests():
	if not request.json or not 'pid' in request.json or not 'userId' in request.json or not 'token' in request.json:
		abort(400, '{"message":"Input parameter incorrect or missing"}')
	pid = request.json['pid']
	userId = request.json['userId']
	token = request.json['token']
	if not utils.authenticateToken(userId, token):
		abort(401)
	
	db = mysql.connect()
	cursor = db.cursor()
	returnList = []
	cursor.execute("SELECT interestUid FROM InterestList WHERE pid = '%s';"%pid) 
	if cursor.rowcount > 0:
		uidList = [item[0] for item in cursor.fetchall()]
		for uid in uidList:
			temp = {}
			userCur = db.cursor()
			userCur.execute("SELECT nickname,avatarURL FROM UserInfo WHERE userId = '%s';"%uid)
			intereP = userCur.fetchall()[0]
			nickname = intereP[0]
			temp['userId'] = uid
			temp['avatarURL'] = intereP[1]
			temp['nickname'] = nickname
			returnList.append(temp)
		db.close()
		return jsonify({'interestList':returnList})
	else :
		db.close()
		abort(400,"Unknown pid")


#author: Wen
@products.route('/products/page', methods=['POST'])
def get_products_by_page():
	if not request.json or not 'pageNum' in request.json or not 'sortBy' in request.json:
		abort(400, '{"message":"Input parameter incorrect or missing"}')
	
	pageNum = int(request.json['pageNum'])
	sortBy = request.json['sortBy']

	if pageNum < 1:
		abort(400, "Incorrect page number")

	pageSize = 20
	if 'pageSize' in request.json:
		pageSize = int(request.json['pageSize'])
	tagRequested = None
	if 'tag' in request.json:
		tagRequested = request.json['tag']

	productsList = []

	if not tagRequested is None:
		db = mysql.connect()
		cursor = db.cursor()
		tagRequested = tagRequested.replace('_', ' ')
		cursor.execute("SELECT tid FROM Tag WHERE tag = '%s';"%tagRequested)
		if cursor.rowcount == 1:
			tid = cursor.fetchall()[0]
			db.close()
		else:
			db.close()
			abort(400,"Incorrect Tag")


	db = mysql.connect()
	cursor = db.cursor()

	if tagRequested is None:
		if sortBy == "priceHighFirst":
			cursor.execute("SELECT * FROM Product ORDER BY pPrice DESC;")
		elif sortBy == "priceLowFirst":
			cursor.execute("SELECT * FROM Product ORDER BY pPrice ASC;")
		elif sortBy == "timeLatestFirst":
			cursor.execute("SELECT * FROM Product ORDER BY postTime DESC;")
		else:
			cursor.execute("SELECT * FROM Product ORDER BY postTime ASC;")
	else:
		if sortBy == "priceHighFirst":
			cursor.execute("SELECT userId, Product.pid, pName, pPrice, pInfo, postTime, usedTime, isSold FROM Product INNER JOIN ProductTag WHERE Product.pid = ProductTag.pid AND ProductTag.tid = '%d' ORDER BY pPrice DESC;"%tid)
		elif sortBy == "priceLowFirst":
			cursor.execute("SELECT userId, Product.pid, pName, pPrice, pInfo, postTime, usedTime, isSold FROM Product INNER JOIN ProductTag WHERE Product.pid = ProductTag.pid AND ProductTag.tid = '%d' ORDER BY pPrice ASC;"%tid)
		elif sortBy == "timeLatestFirst":
			cursor.execute("SELECT userId, Product.pid, pName, pPrice, pInfo, postTime, usedTime, isSold FROM Product INNER JOIN ProductTag WHERE Product.pid = ProductTag.pid AND ProductTag.tid = '%d' ORDER BY postTime DESC;"%tid)
		else:
			cursor.execute("SELECT userId, Product.pid, pName, pPrice, pInfo, postTime, usedTime, isSold FROM Product INNER JOIN ProductTag WHERE Product.pid = ProductTag.pid AND ProductTag.tid = '%d' ORDER BY postTime ASC;"%tid)

	if cursor.rowcount > 0:
		if pageNum > 1:
			cursor.fetchmany(pageSize * (pageNum - 1))
		productList = cursor.fetchmany(pageSize)
		
		for pRow in productList:
			userId = pRow[0]
			pid = pRow[1]
			pName = pRow[2]
			pPrice = str(pRow[3])
			pInfo = pRow[4]
			postTime = pRow[5]
			usedTime = pRow[6]
			isSold = pRow[7]
			imageCur = db.cursor()
			imageCur.execute("SELECT imageURL FROM ProductImage WHERE pid = '%d';"%pid)
			imageList = []
			if imageCur.rowcount > 0:
				imageR = imageCur.fetchall()
				for i in imageR:
					imageList.append(i[0])
			userCur = db.cursor()
			userCur.execute("SELECT nickname FROM UserInfo WHERE userId = '%d';"%userId)
			if userCur.rowcount >0:
				nickname = userCur.fetchall()[0][0]
			currentProduct = {}
			currentProduct['nickname'] = nickname
			currentProduct['userId'] = userId
			currentProduct['pid'] = pid
			currentProduct['pName'] = pName
			currentProduct['pPrice'] = pPrice
			currentProduct['pInfo'] = pInfo
			currentProduct['postTime'] = postTime
			currentProduct['usedTime'] = usedTime
			currentProduct['images'] = imageList
			currentProduct['isSold'] = isSold
			productsList.append(currentProduct)
	db.close()
	return jsonify({'products':productsList})



#author: Wen
@products.route('/products/search', methods=['POST'])
def search():
	if not request.json or not 'keyword' in request.json or not 'pageNum' in request.json:
		abort(400, '{"message":"Input parameter incorrect or missing"}')
	
	keyword = request.json['keyword']
	pageNum = int(request.json['pageNum'])

	if pageNum < 1:
		abort(400, "Incorrect page number")

	pageSize = 20
	if 'pageSize' in request.json:
		pageSize = int(request.json['pageSize'])

	productsList = []

	db = mysql.connect()
	cursor = db.cursor()
	try:
		cursor.execute("SELECT * FROM Product WHERE MATCH (pName) AGAINST ('%s*' IN BOOLEAN MODE);"%keyword)
		
		if cursor.rowcount > 0:
			if pageNum > 1:
				cursor.fetchmany(pageSize * (pageNum - 1))
			productList = cursor.fetchmany(pageSize)
			
			for pRow in productList:
				userId = pRow[0]
				pid = pRow[1]
				pName = pRow[2]
				pPrice = str(pRow[3])
				pInfo = pRow[4]
				postTime = pRow[5]
				usedTime = pRow[6]
				isSold = pRow[7]
				imageCur = db.cursor()
				imageCur.execute("SELECT imageURL FROM ProductImage WHERE pid = '%d';"%pid)
				imageList = []
				if imageCur.rowcount > 0:
					imageR = imageCur.fetchall()
					for i in imageR:
						imageList.append(i[0])
				userCur = db.cursor()
				userCur.execute("SELECT nickname FROM UserInfo WHERE userId = '%d';"%userId)
				if userCur.rowcount >0:
					nickname = userCur.fetchall()[0][0]
				currentProduct = {}
				currentProduct['nickname'] = nickname
				currentProduct['userId'] = userId
				currentProduct['pid'] = pid
				currentProduct['pName'] = pName
				currentProduct['pPrice'] = pPrice
				currentProduct['pInfo'] = pInfo
				currentProduct['postTime'] = postTime
				currentProduct['usedTime'] = usedTime
				currentProduct['images'] = imageList
				currentProduct['isSold'] = isSold
				productsList.append(currentProduct)
		db.close()
		return jsonify({'products':productsList})
	except:
		db.close()
		abort(400, "search failed")


