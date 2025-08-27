from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """
    将明文密码散列化存储。
    """
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    校验输入的密码是否与数据库存储的哈希匹配。
    """
    return pwd_context.verify(plain_password, hashed_password)



if __name__ == "__main__":
    mima = '123456'
    print(hash_password(mima))
    if verify_password('123456', hash_password('123456')):
        print('密码一致')