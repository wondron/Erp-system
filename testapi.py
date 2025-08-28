import requests
import json

def create_new_user(username, showname, password, userrole=None):
    # 接口地址（根据实际部署修改host和port）
    url = "http://47.110.75.108:8000/login/create"  # 假设路由前缀是/login的话需要改为http://localhost:8000/login/create
    
    # 请求体数据
    payload = {
        "username": username,
        "showname": showname,
        "password": password
    }
    
    # 可选参数：如果需要指定用户角色则添加
    if userrole:
        payload["userrole"] = userrole
    
    try:
        # 发送POST请求，JSON格式传递数据
        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        # 打印响应信息
        print(f"状态码: {response.status_code}")
        print(f"响应内容: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        
        # 处理不同响应情况
        if response.status_code == 201:
            print("用户创建成功！")
            return response.json()
        elif response.status_code == 409:
            print(f"创建失败: {response.json()['detail']}")  # 用户已存在
        elif response.status_code == 500:
            print(f"服务器错误: {response.json()['detail']}")
        else:
            print(f"请求失败，状态码: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"请求发生错误: {str(e)}")
    except json.JSONDecodeError:
        print("响应不是有效的JSON格式")

if __name__ == "__main__":
    # 示例调用：创建一个普通用户
    # create_new_user(
    #     username="johndoe",
    #     showname="John Doe",
    #     password="SecurePass123!"
    # )
    
    # 示例调用：创建一个管理员用户（如果角色允许）
    create_new_user(
        username="admin",
        showname="System Admin",
        password="AdminPass456!",
        userrole="ADMIN"  # 假设UserRole枚举中有ADMIN选项
    )
