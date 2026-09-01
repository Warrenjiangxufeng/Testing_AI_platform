from extensions import db
from models import AITestRun, ApiCase, Bug, PerfRun, TestCase


def seed_if_empty():
    if TestCase.query.count() > 0:
        return

    # 功能用例示例
    cases = [
        TestCase(
            name="用户登录-正确账号密码可登录",
            module="用户模块", priority="P1", case_type="功能",
            precondition="已注册有效账号",
            steps="1. 打开登录页\n2. 输入账号密码\n3. 点击登录",
            expected_result="成功进入首页，提示欢迎信息",
            status="通过", creator="管理员",
        ),
        TestCase(
            name="用户登录-错误密码提示明确",
            module="用户模块", priority="P1", case_type="功能",
            precondition="无需预置数据",
            steps="1. 打开登录页\n2. 输入错误密码\n3. 点击登录",
            expected_result="提示'账号或密码错误'，不跳转",
            status="失败", creator="管理员",
        ),
        TestCase(
            name="商品搜索-关键词命中结果",
            module="商品模块", priority="P2", case_type="功能",
            precondition="商品库存在数据",
            steps="1. 进入搜索页\n2. 输入关键词\n3. 点击搜索",
            expected_result="返回包含关键词的商品列表",
            status="待执行", creator="管理员",
        ),
        TestCase(
            name="购物车-添加商品后数量正确",
            module="交易模块", priority="P1", case_type="功能",
            precondition="登录态且商品有库存",
            steps="1. 打开商品详情\n2. 点击加入购物车",
            expected_result="购物车数量加一，角标提示",
            status="草稿", creator="管理员",
        ),
    ]
    db.session.add_all(cases)

    # 接口用例示例（get 示例地址）
    api_cases = [
        ApiCase(
            name="获取用户信息", method="GET",
            url="https://httpbin.org/get",
            headers='{"Content-Type": "application/json"}',
            body="", expected_status=200,
        ),
        ApiCase(
            name="创建订单", method="POST",
            url="https://httpbin.org/post",
            headers='{"Content-Type": "application/json"}',
            body='{"order_id": 1001, "amount": 99.9}',
            expected_status=200,
        ),
    ]
    db.session.add_all(api_cases)

    # 缺陷示例
    bugs = [
        Bug(
            title="点击登录后出现白屏", module="用户模块",
            severity="严重", priority="P1", status="进行中",
            assignee="小李", creator="管理员",
            description="登录按钮点击后页面无响应，控制台报 JS 错误。",
            steps="1. 打开首页\n2. 点击登录\n3. 观察页面",
        ),
        Bug(
            title="搜索接口超时", module="商品模块",
            severity="一般", priority="P2", status="已修复",
            assignee="阿伟", creator="管理员",
            description="商品搜索接口在大量数据时响应超过 10 秒。",
            steps="搜索'手机'关键词记录响应时间",
        ),
    ]
    db.session.add_all(bugs)

    db.session.commit()

