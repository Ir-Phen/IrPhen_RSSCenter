class User()
async def get_dynamics_new()

获取用户动态。

name	type	description

offset	str, optional	该值为第一次调用本方法时，数据中会有个 offset 字段，指向下一动态列表第一条动态（类似单向链表）。根据上一次获取结果中的 next_offset 字段值，循环填充该值即可获取到全部动态。空字符串为从头开始。Defaults to "".

Returns: dict: 调用接口返回的内容。

class OpusType()
Extend: enum.Enum

图文类型

ALL: 所有
ARTICLE: 属于专栏的图文
DYNAMIC: 不属于专栏（但为动态）的图文