import { createElementVNode as _createElementVNode, openBlock as _openBlock, createElementBlock as _createElementBlock, createCommentVNode as _createCommentVNode, toDisplayString as _toDisplayString, createTextVNode as _createTextVNode, renderList as _renderList, Fragment as _Fragment, normalizeClass as _normalizeClass, createStaticVNode as _createStaticVNode } from "vue"

const _hoisted_1 = { class: "page" }
const _hoisted_2 = { class: "card pat" }
const _hoisted_3 = {
  key: 0,
  class: "small dim",
  style: {"margin-top":"10px"}
}
const _hoisted_4 = {
  class: "row wrap pat-stats",
  style: {"gap":"6px"}
}
const _hoisted_5 = { class: "tag" }
const _hoisted_6 = { class: "tag gold" }
const _hoisted_7 = { class: "tag" }
const _hoisted_8 = {
  key: 0,
  class: "tag"
}
const _hoisted_9 = {
  key: 1,
  class: "tag"
}
const _hoisted_10 = { class: "tag" }
const _hoisted_11 = {
  key: 0,
  class: "pat-hint tiny"
}
const _hoisted_12 = {
  key: 1,
  class: "pat-hint tiny info"
}
const _hoisted_13 = {
  key: 2,
  class: "small dim",
  style: {"margin-top":"6px"}
}
const _hoisted_14 = { class: "pat-line1" }
const _hoisted_15 = { class: "pat-name" }
const _hoisted_16 = { class: "pat-chip" }
const _hoisted_17 = {
  key: 0,
  class: "pat-chip core"
}
const _hoisted_18 = {
  key: 1,
  class: "pat-chip flow"
}
const _hoisted_19 = {
  key: 2,
  class: "pat-chip lhb"
}
const _hoisted_20 = {
  key: 3,
  class: "pat-chip dim-chip"
}
const _hoisted_21 = {
  key: 4,
  class: "pat-chip stale"
}
const _hoisted_22 = { class: "pat-line2 tiny dim" }
const _hoisted_23 = {
  key: 0,
  class: "pat-flow tiny"
}
const _hoisted_24 = { class: "dim" }
const _hoisted_25 = { class: "dim" }
const _hoisted_26 = {
  key: 1,
  class: "pat-flow tiny dim"
}
const _hoisted_27 = {
  key: 2,
  class: "pat-lhb tiny"
}
const _hoisted_28 = {
  key: 0,
  class: "lhb-today"
}
const _hoisted_29 = {
  key: 1,
  class: "lhb-prev"
}
const _hoisted_30 = {
  key: 2,
  class: "lhb-det"
}
const _hoisted_31 = { class: "lhb-box" }
const _hoisted_32 = { key: 0 }
const _hoisted_33 = { key: 1 }
const _hoisted_34 = {
  key: 2,
  class: "dim"
}
const _hoisted_35 = { key: 3 }
const _hoisted_36 = { key: 4 }
const _hoisted_37 = { class: "dim" }
const _hoisted_38 = { class: "pat-line1" }
const _hoisted_39 = { class: "pat-name" }
const _hoisted_40 = { class: "pat-chip" }
const _hoisted_41 = {
  key: 0,
  class: "pat-chip core"
}
const _hoisted_42 = { class: "pat-chip dim-chip" }
const _hoisted_43 = {
  key: 1,
  class: "pat-chip lhb"
}
const _hoisted_44 = { class: "pat-line2 tiny dim" }
const _hoisted_45 = {
  key: 0,
  class: "pat-flow tiny dim"
}
const _hoisted_46 = { class: "pat-meta" }
const _hoisted_47 = { class: "pat-meta-body small dim" }
const _hoisted_48 = { key: 0 }
const _hoisted_49 = {
  key: 1,
  style: {"color":"var(--orange)"}
}
const _hoisted_50 = {
  key: 2,
  style: {"color":"var(--orange)"}
}
const _hoisted_51 = {
  key: 3,
  class: "dim"
}
const _hoisted_52 = {
  key: 4,
  style: {"color":"var(--orange)"}
}

export function render(_ctx, _cache) {
  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createElementVNode("div", _hoisted_2, [
      _cache[28] || (_cache[28] = _createStaticVNode("<div class=\"pat-head\"><div class=\"pat-badge\">MA</div><div class=\"grow\"><div class=\"card-title\" style=\"margin:0;\">双线粘合突破 · MA7/MA21</div><div class=\"tiny muted\">腾讯日K前复权 · 粘合 ≤2.5% 持续 ≥3 日 → 收盘上穿 MA21 且 MA7 上翘 · 量能 ≥5日均量×1.5 为确认旗标</div></div></div>", 1)),
      (!_ctx.pt)
        ? (_openBlock(), _createElementBlock("div", _hoisted_3, " 暂无形态数据（仅在最新交易日盘后计算，历史日不补算） "))
        : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
            _createElementVNode("div", _hoisted_4, [
              _createElementVNode("span", _hoisted_5, _toDisplayString(_ctx.s.date) + " 扫描 " + _toDisplayString(_ctx.pt.scan_n) + " 只", 1 /* TEXT */),
              _createElementVNode("span", _hoisted_6, "突破 " + _toDisplayString(_ctx.pt.hit_n), 1 /* TEXT */),
              _createElementVNode("span", _hoisted_7, "粘合观察 " + _toDisplayString(_ctx.pt.watch_n), 1 /* TEXT */),
              (_ctx.flowMeta)
                ? (_openBlock(), _createElementBlock("span", _hoisted_8, "资金流 " + _toDisplayString(_ctx.flowMeta.hit_n) + "/" + _toDisplayString(_ctx.flowMeta.ask_n), 1 /* TEXT */))
                : _createCommentVNode("v-if", true),
              (_ctx.lhbMeta)
                ? (_openBlock(), _createElementBlock("span", _hoisted_9, "龙虎榜 今 " + _toDisplayString(_ctx.lhbMeta.today_n == null ? '—' : _ctx.lhbMeta.today_n) + " · 昨 " + _toDisplayString(_ctx.lhbMeta.prev_n == null ? '—' : _ctx.lhbMeta.prev_n), 1 /* TEXT */))
                : _createCommentVNode("v-if", true),
              _createElementVNode("span", _hoisted_10, _toDisplayString(_ctx.pt.time_ms) + "ms", 1 /* TEXT */)
            ]),
            (_ctx.ebbHint)
              ? (_openBlock(), _createElementBlock("div", _hoisted_11, " 当前周期「" + _toDisplayString(_ctx.stage) + "」" + _toDisplayString(_ctx.band ? '（' + _ctx.band + '）' : '') + "：退潮期整体不建议参与，形态仅作观察，别当买入信号。 ", 1 /* TEXT */))
              : _createCommentVNode("v-if", true),
            (_ctx.lhbMeta && !_ctx.lhbMeta.today_n)
              ? (_openBlock(), _createElementBlock("div", _hoisted_12, [...(_cache[0] || (_cache[0] = [
                  _createTextVNode(" 当日龙虎榜尚未发布（约 18:00 后才出）：本次为盘后 16:05/16:40 快照， ", -1 /* CACHED */),
                  _createElementVNode("b", null, "21:00 夜间任务", -1 /* CACHED */),
                  _createTextVNode("会把当日榜补算进本页。下方「昨上榜」为前一交易日榜，任何时点都可用。 ", -1 /* CACHED */)
                ]))]))
              : _createCommentVNode("v-if", true),
            _cache[26] || (_cache[26] = _createElementVNode("div", { class: "pat-sec tiny muted" }, "突破（粘合后上穿 MA21）· 按资金分排序", -1 /* CACHED */)),
            (!_ctx.hits.length)
              ? (_openBlock(), _createElementBlock("div", _hoisted_13, "今日无标的触发突破"))
              : _createCommentVNode("v-if", true),
            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_ctx.hits, (r) => {
              return (_openBlock(), _createElementBlock("div", {
                key: r.code,
                class: "pat-row hit"
              }, [
                _createElementVNode("div", _hoisted_14, [
                  _createElementVNode("span", _hoisted_15, _toDisplayString(r.name), 1 /* TEXT */),
                  _createElementVNode("span", _hoisted_16, _toDisplayString(r.board) + "板", 1 /* TEXT */),
                  (r.in_core)
                    ? (_openBlock(), _createElementBlock("span", _hoisted_17, "核心"))
                    : _createCommentVNode("v-if", true),
                  _createElementVNode("span", {
                    class: _normalizeClass(["pat-chip vol", r.vol_ok ? 'ok' : ''])
                  }, [
                    _createTextVNode(" 量比 " + _toDisplayString(_ctx.fmt(r.vol_ratio)), 1 /* TEXT */),
                    (r.vol_ok)
                      ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                          _createTextVNode(" · 放量")
                        ], 64 /* STABLE_FRAGMENT */))
                      : _createCommentVNode("v-if", true)
                  ], 2 /* CLASS */),
                  (r.flow_score != null)
                    ? (_openBlock(), _createElementBlock("span", _hoisted_18, "资金分 " + _toDisplayString(r.flow_score), 1 /* TEXT */))
                    : _createCommentVNode("v-if", true),
                  (r.lhb)
                    ? (_openBlock(), _createElementBlock("span", _hoisted_19, "上榜"))
                    : (_ctx.lhbMeta && _ctx.lhbMeta.today_n)
                      ? (_openBlock(), _createElementBlock("span", _hoisted_20, "未上榜"))
                      : _createCommentVNode("v-if", true),
                  (r.stale)
                    ? (_openBlock(), _createElementBlock("span", _hoisted_21, "K线日期=" + _toDisplayString(r.bar_date) + " 可疑", 1 /* TEXT */))
                    : _createCommentVNode("v-if", true)
                ]),
                _createElementVNode("div", _hoisted_22, [
                  _createTextVNode(" 收 " + _toDisplayString(r.close) + "（", 1 /* TEXT */),
                  _createElementVNode("span", {
                    class: _normalizeClass(_ctx.pctCls(r.pct))
                  }, _toDisplayString(_ctx.sign(r.pct)) + _toDisplayString(r.pct) + "%", 3 /* TEXT, CLASS */),
                  _createTextVNode("）· MA7 " + _toDisplayString(r.ma7) + " · MA21 " + _toDisplayString(r.ma21) + " · 粘合 " + _toDisplayString(r.glue) + "% · 已粘合 " + _toDisplayString(r.glue_days) + " 日 ", 1 /* TEXT */)
                ]),
                (r.flow)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_23, [
                      _createElementVNode("span", {
                        class: _normalizeClass(_ctx.pctCls(r.flow.main_net))
                      }, " 主力 " + _toDisplayString(_ctx.money(r.flow.main_net)) + " · 净占比 " + _toDisplayString(_ctx.fmt(r.flow.main_ratio, 2)) + "% ", 3 /* TEXT, CLASS */),
                      _createElementVNode("span", _hoisted_24, " · 超大 " + _toDisplayString(_ctx.money(r.flow.xl_net)) + " / 大 " + _toDisplayString(_ctx.money(r.flow.l_net)) + " / 中 " + _toDisplayString(_ctx.money(r.flow.m_net)) + " / 小 " + _toDisplayString(_ctx.money(r.flow.s_net)), 1 /* TEXT */),
                      _createElementVNode("span", _hoisted_25, [
                        _cache[1] || (_cache[1] = _createTextVNode(" · 近3日 ", -1 /* CACHED */)),
                        _createElementVNode("b", {
                          class: _normalizeClass(_ctx.pctCls(r.flow.sum3))
                        }, _toDisplayString(_ctx.money(r.flow.sum3)), 3 /* TEXT, CLASS */),
                        _cache[2] || (_cache[2] = _createTextVNode(" · 近5日 ", -1 /* CACHED */)),
                        _createElementVNode("b", {
                          class: _normalizeClass(_ctx.pctCls(r.flow.sum5))
                        }, _toDisplayString(_ctx.money(r.flow.sum5)), 3 /* TEXT, CLASS */),
                        _createTextVNode(" · 连续 " + _toDisplayString(r.flow.streak > 0 ? '净流入' + r.flow.streak + '日' : (r.flow.streak < 0 ? '净流出' + (-r.flow.streak) + '日' : '—')), 1 /* TEXT */)
                      ]),
                      _createElementVNode("span", {
                        class: _normalizeClass(["src", r.flow.trend_src === 'sina' ? 'warn' : ''])
                      }, _toDisplayString(_ctx.trendLabel(r.flow)), 3 /* TEXT, CLASS */)
                    ]))
                  : (_openBlock(), _createElementBlock("div", _hoisted_26, "资金流：无数据（北交所旧段 / 停牌 / 接口未返回）")),
                (r.lhb || r.lhb_prev)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_27, [
                      (r.lhb)
                        ? (_openBlock(), _createElementBlock("span", _hoisted_28, [
                            _createTextVNode("上榜 " + _toDisplayString(r.lhb.date) + " ", 1 /* TEXT */),
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(r.lhb.tags, (t, i) => {
                              return (_openBlock(), _createElementBlock("span", {
                                key: i,
                                class: "lhb-tag"
                              }, _toDisplayString(t), 1 /* TEXT */))
                            }), 128 /* KEYED_FRAGMENT */))
                          ]))
                        : _createCommentVNode("v-if", true),
                      (r.lhb_prev)
                        ? (_openBlock(), _createElementBlock("span", _hoisted_29, [
                            _createTextVNode(_toDisplayString(r.lhb ? '· ' : '') + "昨上榜(" + _toDisplayString(r.lhb_prev.date) + ") ", 1 /* TEXT */),
                            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(r.lhb_prev.tags, (t, i) => {
                              return (_openBlock(), _createElementBlock("span", {
                                key: i,
                                class: "lhb-tag prev"
                              }, _toDisplayString(t), 1 /* TEXT */))
                            }), 128 /* KEYED_FRAGMENT */))
                          ]))
                        : _createCommentVNode("v-if", true),
                      (r.lhb)
                        ? (_openBlock(), _createElementBlock("details", _hoisted_30, [
                            _cache[11] || (_cache[11] = _createElementVNode("summary", null, "席位明细", -1 /* CACHED */)),
                            _createElementVNode("div", _hoisted_31, [
                              _createElementVNode("div", null, [
                                _cache[3] || (_cache[3] = _createElementVNode("b", null, "上榜原因", -1 /* CACHED */)),
                                _createTextVNode("：" + _toDisplayString((r.lhb.reasons || []).join('；') || '—'), 1 /* TEXT */)
                              ]),
                              (r.lhb.explain)
                                ? (_openBlock(), _createElementBlock("div", _hoisted_32, [
                                    _cache[4] || (_cache[4] = _createElementVNode("b", null, "资金标签", -1 /* CACHED */)),
                                    _createTextVNode("：" + _toDisplayString(r.lhb.explain), 1 /* TEXT */)
                                  ]))
                                : _createCommentVNode("v-if", true),
                              _createElementVNode("div", null, [
                                _cache[5] || (_cache[5] = _createElementVNode("b", null, "买卖", -1 /* CACHED */)),
                                _createTextVNode("：买 " + _toDisplayString(_ctx.money(r.lhb.buy_amt)) + " / 卖 " + _toDisplayString(_ctx.money(r.lhb.sell_amt)) + " / 净 " + _toDisplayString(_ctx.money(r.lhb.net_amt)) + "（占成交 " + _toDisplayString(_ctx.fmt(r.lhb.net_ratio, 2)) + "%） ", 1 /* TEXT */)
                              ]),
                              (r.lhb.inst)
                                ? (_openBlock(), _createElementBlock("div", _hoisted_33, [
                                    _cache[6] || (_cache[6] = _createElementVNode("b", null, "机构席位", -1 /* CACHED */)),
                                    _createTextVNode("：买 " + _toDisplayString(_ctx.money(r.lhb.inst.buy)) + " / 卖 " + _toDisplayString(_ctx.money(r.lhb.inst.sell)) + " / 净 ", 1 /* TEXT */),
                                    _createElementVNode("b", {
                                      class: _normalizeClass(_ctx.pctCls(r.lhb.inst.net))
                                    }, _toDisplayString(_ctx.money(r.lhb.inst.net)), 3 /* TEXT, CLASS */)
                                  ]))
                                : (_openBlock(), _createElementBlock("div", _hoisted_34, "机构席位：无")),
                              ((r.lhb.seats_buy || []).length)
                                ? (_openBlock(), _createElementBlock("div", _hoisted_35, [
                                    _cache[7] || (_cache[7] = _createElementVNode("b", null, "买入席位", -1 /* CACHED */)),
                                    _cache[8] || (_cache[8] = _createTextVNode("： ", -1 /* CACHED */)),
                                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(r.lhb.seats_buy, (x, i) => {
                                      return (_openBlock(), _createElementBlock("div", {
                                        key: i,
                                        class: "seat"
                                      }, _toDisplayString(x.name) + " — 买 " + _toDisplayString(_ctx.money(x.buy)) + " / 卖 " + _toDisplayString(_ctx.money(x.sell)) + " / 净 " + _toDisplayString(_ctx.money(x.net)), 1 /* TEXT */))
                                    }), 128 /* KEYED_FRAGMENT */))
                                  ]))
                                : _createCommentVNode("v-if", true),
                              ((r.lhb.seats_sell || []).length)
                                ? (_openBlock(), _createElementBlock("div", _hoisted_36, [
                                    _cache[9] || (_cache[9] = _createElementVNode("b", null, "卖出席位", -1 /* CACHED */)),
                                    _cache[10] || (_cache[10] = _createTextVNode("： ", -1 /* CACHED */)),
                                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(r.lhb.seats_sell, (x, i) => {
                                      return (_openBlock(), _createElementBlock("div", {
                                        key: i,
                                        class: "seat"
                                      }, _toDisplayString(x.name) + " — 买 " + _toDisplayString(_ctx.money(x.buy)) + " / 卖 " + _toDisplayString(_ctx.money(x.sell)) + " / 净 " + _toDisplayString(_ctx.money(x.net)), 1 /* TEXT */))
                                    }), 128 /* KEYED_FRAGMENT */))
                                  ]))
                                : _createCommentVNode("v-if", true),
                              _createElementVNode("div", _hoisted_37, " 上榜后：1日 " + _toDisplayString(_ctx.fmt(r.lhb.fwd && r.lhb.fwd.d1, 2)) + "% · 2日 " + _toDisplayString(_ctx.fmt(r.lhb.fwd && r.lhb.fwd.d2, 2)) + "% · 5日 " + _toDisplayString(_ctx.fmt(r.lhb.fwd && r.lhb.fwd.d5, 2)) + "% · 10日 " + _toDisplayString(_ctx.fmt(r.lhb.fwd && r.lhb.fwd.d10, 2)) + "% ", 1 /* TEXT */)
                            ])
                          ]))
                        : _createCommentVNode("v-if", true)
                    ]))
                  : _createCommentVNode("v-if", true)
              ]))
            }), 128 /* KEYED_FRAGMENT */)),
            (_ctx.watch.length)
              ? (_openBlock(), _createElementBlock(_Fragment, { key: 3 }, [
                  _cache[13] || (_cache[13] = _createElementVNode("div", { class: "divider" }, null, -1 /* CACHED */)),
                  _cache[14] || (_cache[14] = _createElementVNode("div", { class: "pat-sec tiny muted" }, "粘合中（尚未突破，观察）", -1 /* CACHED */)),
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_ctx.watch, (r) => {
                    return (_openBlock(), _createElementBlock("div", {
                      key: r.code,
                      class: "pat-row"
                    }, [
                      _createElementVNode("div", _hoisted_38, [
                        _createElementVNode("span", _hoisted_39, _toDisplayString(r.name), 1 /* TEXT */),
                        _createElementVNode("span", _hoisted_40, _toDisplayString(r.board) + "板", 1 /* TEXT */),
                        (r.in_core)
                          ? (_openBlock(), _createElementBlock("span", _hoisted_41, "核心"))
                          : _createCommentVNode("v-if", true),
                        _createElementVNode("span", _hoisted_42, "粘合 " + _toDisplayString(r.glue_days) + " 日", 1 /* TEXT */),
                        (r.lhb)
                          ? (_openBlock(), _createElementBlock("span", _hoisted_43, "上榜"))
                          : _createCommentVNode("v-if", true)
                      ]),
                      _createElementVNode("div", _hoisted_44, [
                        _createTextVNode(" 收 " + _toDisplayString(r.close) + "（", 1 /* TEXT */),
                        _createElementVNode("span", {
                          class: _normalizeClass(_ctx.pctCls(r.pct))
                        }, _toDisplayString(_ctx.sign(r.pct)) + _toDisplayString(r.pct) + "%", 3 /* TEXT, CLASS */),
                        _createTextVNode("）· MA7 " + _toDisplayString(r.ma7) + " · MA21 " + _toDisplayString(r.ma21) + " · 粘合 " + _toDisplayString(r.glue) + "% ", 1 /* TEXT */)
                      ]),
                      (r.flow)
                        ? (_openBlock(), _createElementBlock("div", _hoisted_45, [
                            _cache[12] || (_cache[12] = _createTextVNode(" 主力 ", -1 /* CACHED */)),
                            _createElementVNode("b", {
                              class: _normalizeClass(_ctx.pctCls(r.flow.main_net))
                            }, _toDisplayString(_ctx.money(r.flow.main_net)), 3 /* TEXT, CLASS */),
                            _createTextVNode(" · 净占比 " + _toDisplayString(_ctx.fmt(r.flow.main_ratio, 2)) + "% · 近3日 " + _toDisplayString(_ctx.money(r.flow.sum3)) + " · 连续 " + _toDisplayString(r.flow.streak > 0 ? '净流入' + r.flow.streak + '日' : (r.flow.streak < 0 ? '净流出' + (-r.flow.streak) + '日' : '—')) + " ", 1 /* TEXT */),
                            _createElementVNode("span", {
                              class: _normalizeClass(["src", r.flow.trend_src === 'sina' ? 'warn' : ''])
                            }, _toDisplayString(_ctx.trendLabel(r.flow)), 3 /* TEXT, CLASS */)
                          ]))
                        : _createCommentVNode("v-if", true)
                    ]))
                  }), 128 /* KEYED_FRAGMENT */))
                ], 64 /* STABLE_FRAGMENT */))
              : _createCommentVNode("v-if", true),
            _cache[27] || (_cache[27] = _createElementVNode("div", { class: "divider" }, null, -1 /* CACHED */)),
            _createElementVNode("details", _hoisted_46, [
              _cache[25] || (_cache[25] = _createElementVNode("summary", { class: "tiny muted" }, "口径与免责（务必读一次）", -1 /* CACHED */)),
              _createElementVNode("div", _hoisted_47, [
                _createElementVNode("div", null, "候选池：当日涨停 ∪ 核心池（与 Lab 同池，" + _toDisplayString(_ctx.pt.scan_n) + " 只）。", 1 /* TEXT */),
                _createElementVNode("div", null, "参数：MA" + _toDisplayString(_ctx.pt.params.ma_fast) + " / MA" + _toDisplayString(_ctx.pt.params.ma_slow) + "；粘合阈值 " + _toDisplayString((_ctx.pt.params.glue_pct * 100).toFixed(1)) + "%；持续 ≥" + _toDisplayString(_ctx.pt.params.glue_days) + " 日；放量线 " + _toDisplayString(_ctx.pt.params.vol_mult) + "×。", 1 /* TEXT */),
                _cache[21] || (_cache[21] = _createElementVNode("div", null, [
                  _createTextVNode("K线为"),
                  _createElementVNode("b", null, "前复权"),
                  _createTextVNode("，按本项目惯例仅作形态判断，不与涨跌幅 / 偏离值混用。")
                ], -1 /* CACHED */)),
                _cache[22] || (_cache[22] = _createElementVNode("div", null, [
                  _createTextVNode(" 资金流为"),
                  _createElementVNode("b", null, "东财口径"),
                  _createTextVNode("（主力净额 = 大单 + 超大单），仅加字段并"),
                  _createElementVNode("b", null, "参与排序"),
                  _createTextVNode("， "),
                  _createElementVNode("b", null, "不参与突破判定"),
                  _createTextVNode("（命中数不受影响）。 ")
                ], -1 /* CACHED */)),
                (_ctx.flowMeta && _ctx.flowMeta.srcs)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_48, [
                      _cache[15] || (_cache[15] = _createTextVNode(" 多日趋势来源分布：", -1 /* CACHED */)),
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_ctx.flowMeta.srcs, (n, k) => {
                        return (_openBlock(), _createElementBlock("span", { key: k }, _toDisplayString(k) + "=" + _toDisplayString(n), 1 /* TEXT */))
                      }), 128 /* KEYED_FRAGMENT */)),
                      _cache[16] || (_cache[16] = _createTextVNode("。 ", -1 /* CACHED */)),
                      _cache[17] || (_cache[17] = _createElementVNode("b", null, "agg", -1 /* CACHED */)),
                      _cache[18] || (_cache[18] = _createTextVNode(" = 东财自累积（每日落一行，需连续运行数个交易日）· ", -1 /* CACHED */)),
                      _cache[19] || (_cache[19] = _createElementVNode("b", null, "sina", -1 /* CACHED */)),
                      _cache[20] || (_cache[20] = _createTextVNode(" = 新浪口径兜底（净流入额口径，绝对值与东财不可比，仅看方向/趋势）。 ", -1 /* CACHED */))
                    ]))
                  : _createCommentVNode("v-if", true),
                _cache[23] || (_cache[23] = _createElementVNode("div", null, [
                  _createTextVNode(" 龙虎榜：当日榜（T，约 18:00 后发布，16:05/16:40 快照为空，21:00 夜间任务补算） 与前一交易日榜（T-1）"),
                  _createElementVNode("b", null, "两者都存"),
                  _createTextVNode("；上榜加标签，未上榜按常态处理。 净买/净卖为"),
                  _createElementVNode("b", null, "龙虎榜席位口径"),
                  _createTextVNode("，非全市场资金流。 ")
                ], -1 /* CACHED */)),
                (_ctx.flowMeta && _ctx.flowMeta.errors && _ctx.flowMeta.errors.length)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_49, "资金流部分失败：" + _toDisplayString(_ctx.flowMeta.errors.join('；')), 1 /* TEXT */))
                  : _createCommentVNode("v-if", true),
                (_ctx.lhbMeta && _ctx.lhbMeta.errors && _ctx.lhbMeta.errors.length)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_50, "龙虎榜部分失败：" + _toDisplayString(_ctx.lhbMeta.errors.join('；')), 1 /* TEXT */))
                  : _createCommentVNode("v-if", true),
                (_ctx.pt.flow_rows)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_51, "当日已落库资金流样本 " + _toDisplayString(_ctx.pt.flow_rows.length) + " 条（供次日算多日累计）。", 1 /* TEXT */))
                  : _createCommentVNode("v-if", true),
                (_ctx.pt.errors && _ctx.pt.errors.length)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_52, "部分标的取数失败：" + _toDisplayString(_ctx.pt.errors.join('；')), 1 /* TEXT */))
                  : _createCommentVNode("v-if", true),
                _cache[24] || (_cache[24] = _createElementVNode("div", { style: {"margin-top":"4px"} }, "纯技术形态 + 资金/席位辅助，供研究参考，不构成投资建议；需与周期定位、Lab 排雷、verb 风控交叉验证后使用。", -1 /* CACHED */))
              ])
            ])
          ], 64 /* STABLE_FRAGMENT */))
    ])
  ]))
}