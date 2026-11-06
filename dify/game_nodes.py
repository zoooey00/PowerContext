"""这些函数的源码直接嵌入 Dify Code 节点；网关不导入本文件。"""

def input_node(player: str, save_code: str, query: str, request_id: str) -> dict:
    import hashlib
    import json
    if len(save_code) < 24 or len(save_code) > 128:
        raise ValueError('存档口令须为 24–128 字符的随机字符串，请勿使用真实账号密码')
    if not player.strip() or len(player) > 40:
        raise ValueError('存档名须为 1–40 字')
    prefix, sep, value = query.strip().replace('：', ':', 1).partition(':')
    actions = {'恶作剧': 'prank', '交换': 'trade', '道歉': 'apologize', '看看': 'look'}
    action = actions.get(prefix, 'look')
    item = value.strip() if sep and prefix in actions else query.strip()
    if not item or len(item) > 150:
        raise ValueError('行动内容须为 1–150 字')
    namespace = hashlib.sha256((save_code + '\0' + player.strip()).encode()).hexdigest()
    command = json.dumps({'action': action, 'item': item}, ensure_ascii=False)
    return {'body': json.dumps({'namespace': namespace, 'request_id': request_id}), 'command': command}


def settle_node(body: str, status_code: int, command: str) -> dict:
    import json
    if status_code != 200:
        raise ValueError('记忆读取失败，未结算')
    memory = json.loads(body)
    rows = memory['records']
    # 所有游戏状态从实际经历重放；不相信网关提供的分数或价钱。
    suspicion = 0
    for index, row in enumerate(rows, 1):
        if row['turn'] != index:
            raise ValueError('存档事件不连续')
        suspicion = max(0, min(5, suspicion + {'prank': 2, 'apologize': -1}.get(row['action'], 0)))
    action = json.loads(command)
    allowed = 'yes' if len(rows) < 20 else 'no'
    before = {'turn': len(rows), 'suspicion': suspicion, 'price': 3 + 2 * suspicion}
    suspicion = max(0, min(5, suspicion + {'prank': 2, 'apologize': -1}.get(action['action'], 0)))
    after = {'turn': len(rows) + 1, 'suspicion': suspicion, 'price': 3 + 2 * suspicion,
             'badge': '老冤家' if suspicion >= 4 else '熟客'}
    prize = ['打嗝消音罩', '失眠计数器', '月光收纳袋'][(len(rows)) % 3]
    labels = {'prank': '恶作剧道具', 'trade': '交换报价物品', 'apologize': '道歉礼物', 'look': '查看目标'}
    event = {'turn': after['turn'], 'action': action['action'], 'item': action['item'], 'after': after,
             'exchange': {'offered': action['item'], 'received': prize} if action['action'] == 'trade' else None}
    # 历史台账在代码中准确渲染。模型永远不能改写它。
    facts = []
    for r in rows[-5:]:
        line = '第 %s 回合｜%s：%s' % (r['turn'], labels[r['action']], json.dumps(r['item'], ensure_ascii=False))
        if r['exchange']:
            line += '；实际换得：' + r['exchange']['received']
        facts.append(line)
    safe_model_context = {'action': action['action'], 'suspicion': suspicion, 'returning': bool(rows)}
    return {'allowed': allowed, 'ticket': memory['ticket'], 'event': json.dumps(event, ensure_ascii=False),
            'history': '\n'.join(facts) or '首次进店，没有历史。',
            'context': json.dumps(safe_model_context), 'before': json.dumps(before),
            'limit_message': '本存档已完成 20 回合。请用新存档名与新随机口令开始新故事。'}


def render_node(ticket: str, event: str, history: str, model: str) -> dict:
    import json
    e = json.loads(event)
    # 只消费有限枚举；模型的其他文字（包括伪造历史、注入文本）一律不展示、不存储。
    try:
        tone = json.loads(model).get('tone')
    except (ValueError, TypeError, AttributeError):
        tone = None
    phrases = {'astonished': '阿扣的纸箱盖弹了起来：“好家伙，今天柜台又要加固了！”',
               'stern': '阿扣敲了敲纽扣罐：“规矩贴在这里，纸箱精也有原则！”',
               'soft': '阿扣把纽扣罐往身后藏：“哼，算你有点诚意。”'}
    reaction = phrases.get(tone, '阿扣扶正纸箱盖：“咱们按账本来。”')
    item = json.dumps(e['item'], ensure_ascii=False)
    if e['action'] == 'prank':
        scene = '你用 %s 恶作剧。阿扣启动了柜台防恶作剧铃。本轮没有发生物品交换。' % item
    elif e['action'] == 'trade':
        scene = '本次交换：你交出 %s，换得「%s」。其他历史道具不参与这次交换。' % (item, e['exchange']['received'])
    elif e['action'] == 'apologize':
        scene = '你带来 %s 赔礼，阿扣收下道歉，警惕降低。本轮没有发生物品交换。' % item
    else:
        scene = '你查看 %s，阿扣展示柜台上的怪东西。本轮没有发生物品交换。' % item
    s = e['after']
    answer = reaction + '\n\n【本轮事件】\n' + scene + '\n\n【历史账本：只读】\n' + history
    answer += '\n\n第 %s 回合 · 警惕 %s/5 · 交换价 %s 枚纽扣 · %s' % (s['turn'], s['suspicion'], s['price'], s['badge'])
    answer += '\n下回可以发送「交换：怪物品」「道歉：礼物」或「恶作剧：道具」。'
    e['reply'] = answer
    return {'body': json.dumps({'ticket': ticket, 'record': e}, ensure_ascii=False), 'answer': answer,
            'model_guard': 'accepted' if tone in phrases else 'fallback'}


def receipt_node(body: str, status_code: int, answer: str) -> dict:
    import json
    if status_code != 200 or json.loads(body).get('saved') is not True:
        raise ValueError('记忆写入未确认，不能显示成功收据')
    return {'answer': answer + '\n记忆已保存，下次进入同一存档仍有效。'}
