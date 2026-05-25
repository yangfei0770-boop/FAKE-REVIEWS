from corrector import correct

news_list = [
    {
        "title": "塔利班颁布新婚姻法，含童婚条款",
        "content": """
        联合国对阿富汗塔利班政府颁布的新婚姻法表示"严重关切"。
        该法律包含童婚条款，并对离婚中的女性权利进行新的限制。
        塔利班自2021年重新掌权以来持续限制女性接受教育、工作和出行的权利。
        国际社会谴责该法律，但塔利班称其符合伊斯兰教法。
        """,
        "keyword": "Taliban child marriage law women 2026"
    },
    {
        "title": "中国山西煤矿爆炸，至少82人遇难",
        "content": """
        中国山西省一煤矿发生瓦斯爆炸，造成至少82人死亡。
        金正恩向习近平发去慰问电。
        中国是全球煤矿事故最频发的国家之一，
        尽管官方多次宣布加强安全监管，事故仍持续发生。
        矿工大多来自农村，是家庭的主要经济来源。
        """,
        "keyword": "山西煤矿爆炸 矿工 事故 site:x.com"
    },
    {
        "title": "特朗普宣布绿卡政策突变：外国人须回国申请",
        "content": """
        特朗普政府宣布，在美外国人若想申请绿卡，
        必须离开美国回到本国重新申请，废除沿用多年的境内调整身份政策。
        此举影响数百万在美合法居留的外国人，包括大量持工作签证的科技工人。
        移民律师称此为"突然袭击"，许多人将被迫面临家庭分离。
        """,
        "keyword": "green card policy change Trump 2026 immigrants site:x.com"
    },
]

for item in news_list:
    print(f"\n{'█' * 60}")
    print(f"新闻：{item['title']}")
    print('█' * 60)
    result = correct(item["content"], item["keyword"])
    print("\n【Fake Review】")
    print(result["fake_review"])
    print("\n【矫正】")
    print(result["correction"])
