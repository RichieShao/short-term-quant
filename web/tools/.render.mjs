import { createElementVNode as _createElementVNode, openBlock as _openBlock, createElementBlock as _createElementBlock, createCommentVNode as _createCommentVNode, toDisplayString as _toDisplayString, createTextVNode as _createTextVNode, Fragment as _Fragment, renderList as _renderList, normalizeClass as _normalizeClass, createStaticVNode as _createStaticVNode } from "vue"

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
  class: "tag stale"
}
const _hoisted_10 = {
  key: 2,
  class: "tag"
}
const _hoisted_11 = {
  key: 3,
  class: "tag"
}
const _hoisted_12 = { class: "tag" }
const _hoisted_13 = {
  key: 0,
  class: "pat-hint tiny"
}
const _hoisted_14 = {
  key: 1,
  class: "pat-hint tiny"
}
const _hoisted_15 = { class: "stale-det" }
const _hoisted_16 = {
  key: 0,
  class: "dim"
}
const _hoisted_17 = {
  key: 2,
  class: "pat-hint tiny info"
}
const _hoisted_18 = {
  key: 3,
  class: "pat-hint tiny info"
}
const _hoisted_19 = {
  key: 4,
  class: "small dim",
  style: {"margin-top":"6px"}
}
const _hoisted_20 = { class: "pat-line1" }
const _hoisted_21 = { class: "pat-name" }
const _hoisted_22 = {
  key: 0,
  class: "pat-chip"
}
const _hoisted_23 = {
  key: 1,
  class: "pat-chip act"
}
const _hoisted_24 = {
  key: 2,
  class: "pat-chip core"
}
const _hoisted_25 = {
  key: 3,
  class: "pat-chip flow"
}
const _hoisted_26 = {
  key: 4,
  class: "pat-chip lhb"
}
const _hoisted_27 = {
  key: 5,
  class: "pat-chip dim-chip"
}
const _hoisted_28 = { class: "pat-line2 tiny dim" }
const _hoisted_29 = {
  key: 0,
  class: "pat-flow tiny"
}
const _hoisted_30 = { class: "dim" }
const _hoisted_31 = { class: "dim" }
const _hoisted_32 = {
  key: 1,
  class: "pat-flow tiny dim"
}
const _hoisted_33 = {
  key: 2,
  class: "pat-lhb tiny"
}
const _hoisted_34 = {
  key: 0,
  class: "lhb-today"
}
const _hoisted_35 = {
  key: 1,
  class: "lhb-prev"
}
const _hoisted_36 = {
  key: 2,
  class: "lhb-det"
}
const _hoisted_37 = { class: "lhb-box" }
const _hoisted_38 = { key: 0 }
const _hoisted_39 = { key: 1 }
const _hoisted_40 = {
  key: 2,
  class: "dim"
}
const _hoisted_41 = { key: 3 }
const _hoisted_42 = { key: 4 }
const _hoisted_43 = { class: "dim" }
const _hoisted_44 = { class: "pat-line1" }
const _hoisted_45 = { class: "pat-name" }
const _hoisted_46 = {
  key: 0,
  class: "pat-chip"
}
const _hoisted_47 = {
  key: 1,
  class: "pat-chip act"
}
const _hoisted_48 = {
  key: 2,
  class: "pat-chip core"
}
const _hoisted_49 = { class: "pat-chip dim-chip" }
const _hoisted_50 = {
  key: 3,
  class: "pat-chip lhb"
}
const _hoisted_51 = { class: "pat-line2 tiny dim" }
const _hoisted_52 = {
  key: 0,
  class: "pat-flow tiny dim"
}
const _hoisted_53 = { class: "pat-meta" }
const _hoisted_54 = { class: "pat-meta-body small dim" }
const _hoisted_55 = { key: 0 }
const _hoisted_56 = {
  key: 0,
  style: {"color":"var(--orange)"}
}
const _hoisted_57 = { key: 1 }
const _hoisted_58 = { key: 2 }
const _hoisted_59 = {
  key: 1,
  style: {"color":"var(--orange)"}
}
const _hoisted_60 = { key: 3 }
const _hoisted_61 = {
  key: 4,
  style: {"color":"var(--orange)"}
}
const _hoisted_62 = {
  key: 5,
  style: {"color":"var(--orange)"}
}
const _hoisted_63 = {
  key: 6,
  class: "dim"
}
const _hoisted_64 = {
  key: 7,
  style: {"color":"var(--orange)"}
}

export function render(_ctx, _cache) {
  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createElementVNode("div", _hoisted_2, [
      _cache[44] || (_cache[44] = _createStaticVNode("<div class=\"pat-head\"><div class=\"pat-badge\">MA</div><div class=\"grow\"><div class=\"card-title\" style=\"margin:0;\">双线粘合突破 · MA7/MA21</div><div class=\"tiny muted\">腾讯日K前复权 · 粘合 ≤2.5% 持续 ≥3 日 → 收盘上穿 MA21 且 MA7 上翘 · 量能 ≥5日均量×1.5 为确认旗标</div></div></div>", 1)),
      (!_ctx.pt)
        ? (_openBlock(), _createElementBlock("div", _hoisted_3, " 暂无形态数据（仅在最新交易日盘后计算，历史日不补算） "))
        : (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
            _createElementVNode("div", _hoisted_4, [
              _createElementVNode("span", _hoisted_5, _toDisplayString(_ctx.s.date) + " 扫描 " + _toDisplayString(_ctx.pt.scan_n) + " 只", 1 /* TEXT */),
              _createElementVNode("span", _hoisted_6, "突破 " + _toDisplayString(_ctx.pt.hit_n), 1 /* TEXT */),
              _createElementVNode("span", _hoisted_7, "粘合观察 " + _toDisplayString(_ctx.pt.watch_n), 1 /* TEXT */),
              (_ctx.poolMeta)
                ? (_openBlock(), _createElementBlock("span", _hoisted_8, [
                    _createTextVNode(" 池 涨停" + _toDisplayString(_ctx.poolMeta.zt_n), 1 /* TEXT */),
                    (_ctx.poolMeta.active_n)
                      ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                          _createTextVNode(" + 异动" + _toDisplayString(_ctx.poolMeta.active_n), 1 /* TEXT */)
                        ], 64 /* STABLE_FRAGMENT */))
                      : _createCommentVNode("v-if", true),
                    (_ctx.poolMeta.core_n)
                      ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                          _createTextVNode(" + 核心" + _toDisplayString(_ctx.poolMeta.core_n), 1 /* TEXT */)
                        ], 64 /* STABLE_FRAGMENT */))
                      : _createCommentVNode("v-if", true)
                  ]))
                : _createCommentVNode("v-if", true),
              (_ctx.pt.stale_n)
                ? (_openBlock(), _createElementBlock("span", _hoisted_9, "滞后 " + _toDisplayString(_ctx.pt.stale_n), 1 /* TEXT */))
                : _createCommentVNode("v-if", true),
              (_ctx.flowMeta)
                ? (_openBlock(), _createElementBlock("span", _hoisted_10, "资金流 " + _toDisplayString(_ctx.flowMeta.hit_n) + "/" + _toDisplayString(_ctx.flowMeta.ask_n), 1 /* TEXT */))
                : _createCommentVNode("v-if", true),
              (_ctx.lhbMeta)
                ? (_openBlock(), _createElementBlock("span", _hoisted_11, "龙虎榜 今 " + _toDisplayString(_ctx.lhbMeta.today_n == null ? '—' : _ctx.lhbMeta.today_n) + " · 昨 " + _toDisplayString(_ctx.lhbMeta.prev_n == null ? '—' : _ctx.lhbMeta.prev_n), 1 /* TEXT */))
                : _createCommentVNode("v-if", true),
              _createElementVNode("span", _hoisted_12, _toDisplayString(_ctx.pt.time_ms) + "ms", 1 /* TEXT */)
            ]),
            (_ctx.ebbHint)
              ? (_openBlock(), _createElementBlock("div", _hoisted_13, " 当前周期「" + _toDisplayString(_ctx.stage) + "」" + _toDisplayString(_ctx.band ? '（' + _ctx.band + '）' : '') + "：退潮期整体不建议参与，形态仅作观察，别当买入信号。 ", 1 /* TEXT */))
              : _createCommentVNode("v-if", true),
            _createCommentVNode(" P3：K线新鲜度守卫 "),
            (_ctx.pt.fresh === false)
              ? (_openBlock(), _createElementBlock("div", _hoisted_14, [
                  _cache[1] || (_cache[1] = _createTextVNode(" ⚠ 有 ", -1 /* CACHED */)),
                  _createElementVNode("b", null, _toDisplayString(_ctx.pt.stale_n), 1 /* TEXT */),
                  _createTextVNode(" 只标的的 K 线最后一根不是 " + _toDisplayString(_ctx.pt.date) + "（停牌 / 行情未更新）， 已", 1 /* TEXT */),
                  _cache[2] || (_cache[2] = _createElementVNode("b", null, "全部剔除、不产出信号", -1 /* CACHED */)),
                  _cache[3] || (_cache[3] = _createTextVNode("——避免用旧 bar 算出\"假突破\"。 ", -1 /* CACHED */)),
                  (_ctx.pt.latest_bar)
                    ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                        _createTextVNode("当前池内最新 K 线日：" + _toDisplayString(_ctx.pt.latest_bar) + "。", 1 /* TEXT */)
                      ], 64 /* STABLE_FRAGMENT */))
                    : _createCommentVNode("v-if", true),
                  _createElementVNode("details", _hoisted_15, [
                    _cache[0] || (_cache[0] = _createElementVNode("summary", null, "查看剔除清单", -1 /* CACHED */)),
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_ctx.staleCodes, (x) => {
                      return (_openBlock(), _createElementBlock("div", {
                        key: x.code,
                        class: "seat"
                      }, _toDisplayString(x.code) + " " + _toDisplayString(x.name) + " — K线最后日 " + _toDisplayString(x.bar_date), 1 /* TEXT */))
                    }), 128 /* KEYED_FRAGMENT */)),
                    (_ctx.pt.stale_n > _ctx.staleCodes.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_16, "…另 " + _toDisplayString(_ctx.pt.stale_n - _ctx.staleCodes.length) + " 只", 1 /* TEXT */))
                      : _createCommentVNode("v-if", true)
                  ])
                ]))
              : _createCommentVNode("v-if", true),
            (_ctx.lhbMeta && !_ctx.lhbMeta.today_n)
              ? (_openBlock(), _createElementBlock("div", _hoisted_17, [...(_cache[4] || (_cache[4] = [
                  _createTextVNode(" 当日龙虎榜尚未发布（约 18:00 后才出）：本次为盘后 16:05/16:40 快照， ", -1 /* CACHED */),
                  _createElementVNode("b", null, "21:00 夜间任务", -1 /* CACHED */),
                  _createTextVNode("会把当日榜补算进本页。下方「昨上榜」为前一交易日榜，任何时点都可用。 ", -1 /* CACHED */)
                ]))]))
              : _createCommentVNode("v-if", true),
            (_ctx.flowMeta && _ctx.flowMeta.sina_blocked)
              ? (_openBlock(), _createElementBlock("div", _hoisted_18, [...(_cache[5] || (_cache[5] = [
                  _createTextVNode(" 新浪资金流接口本次已触发反爬限流：多日累计（近3/5日、连续天数）整体缺失， 资金分已自动降为「可用项重新加权」（看每行的「N项」标记）。 ", -1 /* CACHED */),
                  _createElementVNode("b", null, "长期解是东财自累积", -1 /* CACHED */),
                  _createTextVNode("——每交易日落一行，约 3 个交易日后 agg 会接管、不再依赖新浪。 ", -1 /* CACHED */)
                ]))]))
              : _createCommentVNode("v-if", true),
            _cache[42] || (_cache[42] = _createElementVNode("div", { class: "pat-sec tiny muted" }, "突破（粘合后上穿 MA21）· 按资金分排序", -1 /* CACHED */)),
            (!_ctx.hits.length)
              ? (_openBlock(), _createElementBlock("div", _hoisted_19, "今日无标的触发突破"))
              : _createCommentVNode("v-if", true),
            (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_ctx.hits, (r) => {
              return (_openBlock(), _createElementBlock("div", {
                key: r.code,
                class: "pat-row hit"
              }, [
                _createElementVNode("div", _hoisted_20, [
                  _createElementVNode("span", _hoisted_21, _toDisplayString(r.name), 1 /* TEXT */),
                  (r.pool === 'zt')
                    ? (_openBlock(), _createElementBlock("span", _hoisted_22, _toDisplayString(r.board) + "板", 1 /* TEXT */))
                    : (r.pool === 'active')
                      ? (_openBlock(), _createElementBlock("span", _hoisted_23, "放量"))
                      : _createCommentVNode("v-if", true),
                  (r.in_core)
                    ? (_openBlock(), _createElementBlock("span", _hoisted_24, "核心"))
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
                    ? (_openBlock(), _createElementBlock("span", _hoisted_25, [
                        _createTextVNode(" 资金分 " + _toDisplayString(r.flow_score), 1 /* TEXT */),
                        (r.flow_parts > 0 && r.flow_parts < 3)
                          ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                              _createTextVNode("·" + _toDisplayString(r.flow_parts) + "项", 1 /* TEXT */)
                            ], 64 /* STABLE_FRAGMENT */))
                          : _createCommentVNode("v-if", true)
                      ]))
                    : _createCommentVNode("v-if", true),
                  (r.lhb)
                    ? (_openBlock(), _createElementBlock("span", _hoisted_26, "上榜"))
                    : (_ctx.lhbMeta && _ctx.lhbMeta.today_n)
                      ? (_openBlock(), _createElementBlock("span", _hoisted_27, "未上榜"))
                      : _createCommentVNode("v-if", true)
                ]),
                _createElementVNode("div", _hoisted_28, [
                  _createTextVNode(" 收 " + _toDisplayString(r.close) + "（", 1 /* TEXT */),
                  _createElementVNode("span", {
                    class: _normalizeClass(_ctx.pctCls(r.pct))
                  }, _toDisplayString(_ctx.sign(r.pct)) + _toDisplayString(r.pct) + "%", 3 /* TEXT, CLASS */),
                  _createTextVNode("）· MA7 " + _toDisplayString(r.ma7) + " · MA21 " + _toDisplayString(r.ma21) + " · 粘合 " + _toDisplayString(r.glue) + "% · 已粘合 " + _toDisplayString(r.glue_days) + " 日 ", 1 /* TEXT */)
                ]),
                (r.flow)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_29, [
                      _createElementVNode("span", {
                        class: _normalizeClass(_ctx.pctCls(r.flow.main_net))
                      }, " 主力 " + _toDisplayString(_ctx.money(r.flow.main_net)) + " · 净占比 " + _toDisplayString(_ctx.fmt(r.flow.main_ratio, 2)) + "% ", 3 /* TEXT, CLASS */),
                      _createElementVNode("span", _hoisted_30, " · 超大 " + _toDisplayString(_ctx.money(r.flow.xl_net)) + " / 大 " + _toDisplayString(_ctx.money(r.flow.l_net)) + " / 中 " + _toDisplayString(_ctx.money(r.flow.m_net)) + " / 小 " + _toDisplayString(_ctx.money(r.flow.s_net)), 1 /* TEXT */),
                      _createElementVNode("span", _hoisted_31, [
                        _cache[6] || (_cache[6] = _createTextVNode(" · 近3日 ", -1 /* CACHED */)),
                        _createElementVNode("b", {
                          class: _normalizeClass(_ctx.pctCls(r.flow.sum3))
                        }, _toDisplayString(_ctx.money(r.flow.sum3)), 3 /* TEXT, CLASS */),
                        _cache[7] || (_cache[7] = _createTextVNode(" · 近5日 ", -1 /* CACHED */)),
                        _createElementVNode("b", {
                          class: _normalizeClass(_ctx.pctCls(r.flow.sum5))
                        }, _toDisplayString(_ctx.money(r.flow.sum5)), 3 /* TEXT, CLASS */),
                        _createTextVNode(" · 连续 " + _toDisplayString(r.flow.streak > 0 ? '净流入' + r.flow.streak + '日' : (r.flow.streak < 0 ? '净流出' + (-r.flow.streak) + '日' : '—')), 1 /* TEXT */)
                      ]),
                      _createElementVNode("span", {
                        class: _normalizeClass(["src", r.flow.trend_src === 'sina' ? 'warn' : ''])
                      }, _toDisplayString(_ctx.trendLabel(r.flow)), 3 /* TEXT, CLASS */)
                    ]))
                  : (_openBlock(), _createElementBlock("div", _hoisted_32, "资金流：无数据（北交所旧段 / 停牌 / 接口未返回）")),
                (r.lhb || r.lhb_prev)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_33, [
                      (r.lhb)
                        ? (_openBlock(), _createElementBlock("span", _hoisted_34, [
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
                        ? (_openBlock(), _createElementBlock("span", _hoisted_35, [
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
                        ? (_openBlock(), _createElementBlock("details", _hoisted_36, [
                            _cache[16] || (_cache[16] = _createElementVNode("summary", null, "席位明细", -1 /* CACHED */)),
                            _createElementVNode("div", _hoisted_37, [
                              _createElementVNode("div", null, [
                                _cache[8] || (_cache[8] = _createElementVNode("b", null, "上榜原因", -1 /* CACHED */)),
                                _createTextVNode("：" + _toDisplayString((r.lhb.reasons || []).join('；') || '—'), 1 /* TEXT */)
                              ]),
                              (r.lhb.explain)
                                ? (_openBlock(), _createElementBlock("div", _hoisted_38, [
                                    _cache[9] || (_cache[9] = _createElementVNode("b", null, "资金标签", -1 /* CACHED */)),
                                    _createTextVNode("：" + _toDisplayString(r.lhb.explain), 1 /* TEXT */)
                                  ]))
                                : _createCommentVNode("v-if", true),
                              _createElementVNode("div", null, [
                                _cache[10] || (_cache[10] = _createElementVNode("b", null, "买卖", -1 /* CACHED */)),
                                _createTextVNode("：买 " + _toDisplayString(_ctx.money(r.lhb.buy_amt)) + " / 卖 " + _toDisplayString(_ctx.money(r.lhb.sell_amt)) + " / 净 " + _toDisplayString(_ctx.money(r.lhb.net_amt)) + "（占成交 " + _toDisplayString(_ctx.fmt(r.lhb.net_ratio, 2)) + "%） ", 1 /* TEXT */)
                              ]),
                              (r.lhb.inst)
                                ? (_openBlock(), _createElementBlock("div", _hoisted_39, [
                                    _cache[11] || (_cache[11] = _createElementVNode("b", null, "机构席位", -1 /* CACHED */)),
                                    _createTextVNode("：买 " + _toDisplayString(_ctx.money(r.lhb.inst.buy)) + " / 卖 " + _toDisplayString(_ctx.money(r.lhb.inst.sell)) + " / 净 ", 1 /* TEXT */),
                                    _createElementVNode("b", {
                                      class: _normalizeClass(_ctx.pctCls(r.lhb.inst.net))
                                    }, _toDisplayString(_ctx.money(r.lhb.inst.net)), 3 /* TEXT, CLASS */)
                                  ]))
                                : (_openBlock(), _createElementBlock("div", _hoisted_40, "机构席位：无")),
                              ((r.lhb.seats_buy || []).length)
                                ? (_openBlock(), _createElementBlock("div", _hoisted_41, [
                                    _cache[12] || (_cache[12] = _createElementVNode("b", null, "买入席位", -1 /* CACHED */)),
                                    _cache[13] || (_cache[13] = _createTextVNode("： ", -1 /* CACHED */)),
                                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(r.lhb.seats_buy, (x, i) => {
                                      return (_openBlock(), _createElementBlock("div", {
                                        key: i,
                                        class: "seat"
                                      }, _toDisplayString(x.name) + " — 买 " + _toDisplayString(_ctx.money(x.buy)) + " / 卖 " + _toDisplayString(_ctx.money(x.sell)) + " / 净 " + _toDisplayString(_ctx.money(x.net)), 1 /* TEXT */))
                                    }), 128 /* KEYED_FRAGMENT */))
                                  ]))
                                : _createCommentVNode("v-if", true),
                              ((r.lhb.seats_sell || []).length)
                                ? (_openBlock(), _createElementBlock("div", _hoisted_42, [
                                    _cache[14] || (_cache[14] = _createElementVNode("b", null, "卖出席位", -1 /* CACHED */)),
                                    _cache[15] || (_cache[15] = _createTextVNode("： ", -1 /* CACHED */)),
                                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(r.lhb.seats_sell, (x, i) => {
                                      return (_openBlock(), _createElementBlock("div", {
                                        key: i,
                                        class: "seat"
                                      }, _toDisplayString(x.name) + " — 买 " + _toDisplayString(_ctx.money(x.buy)) + " / 卖 " + _toDisplayString(_ctx.money(x.sell)) + " / 净 " + _toDisplayString(_ctx.money(x.net)), 1 /* TEXT */))
                                    }), 128 /* KEYED_FRAGMENT */))
                                  ]))
                                : _createCommentVNode("v-if", true),
                              _createElementVNode("div", _hoisted_43, " 上榜后：1日 " + _toDisplayString(_ctx.fmt(r.lhb.fwd && r.lhb.fwd.d1, 2)) + "% · 2日 " + _toDisplayString(_ctx.fmt(r.lhb.fwd && r.lhb.fwd.d2, 2)) + "% · 5日 " + _toDisplayString(_ctx.fmt(r.lhb.fwd && r.lhb.fwd.d5, 2)) + "% · 10日 " + _toDisplayString(_ctx.fmt(r.lhb.fwd && r.lhb.fwd.d10, 2)) + "% ", 1 /* TEXT */)
                            ])
                          ]))
                        : _createCommentVNode("v-if", true)
                    ]))
                  : _createCommentVNode("v-if", true)
              ]))
            }), 128 /* KEYED_FRAGMENT */)),
            (_ctx.watch.length)
              ? (_openBlock(), _createElementBlock(_Fragment, { key: 5 }, [
                  _cache[18] || (_cache[18] = _createElementVNode("div", { class: "divider" }, null, -1 /* CACHED */)),
                  _cache[19] || (_cache[19] = _createElementVNode("div", { class: "pat-sec tiny muted" }, "粘合中（尚未突破，观察）", -1 /* CACHED */)),
                  (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_ctx.watch, (r) => {
                    return (_openBlock(), _createElementBlock("div", {
                      key: r.code,
                      class: "pat-row"
                    }, [
                      _createElementVNode("div", _hoisted_44, [
                        _createElementVNode("span", _hoisted_45, _toDisplayString(r.name), 1 /* TEXT */),
                        (r.pool === 'zt')
                          ? (_openBlock(), _createElementBlock("span", _hoisted_46, _toDisplayString(r.board) + "板", 1 /* TEXT */))
                          : (r.pool === 'active')
                            ? (_openBlock(), _createElementBlock("span", _hoisted_47, "放量"))
                            : _createCommentVNode("v-if", true),
                        (r.in_core)
                          ? (_openBlock(), _createElementBlock("span", _hoisted_48, "核心"))
                          : _createCommentVNode("v-if", true),
                        _createElementVNode("span", _hoisted_49, "粘合 " + _toDisplayString(r.glue_days) + " 日", 1 /* TEXT */),
                        (r.lhb)
                          ? (_openBlock(), _createElementBlock("span", _hoisted_50, "上榜"))
                          : _createCommentVNode("v-if", true)
                      ]),
                      _createElementVNode("div", _hoisted_51, [
                        _createTextVNode(" 收 " + _toDisplayString(r.close) + "（", 1 /* TEXT */),
                        _createElementVNode("span", {
                          class: _normalizeClass(_ctx.pctCls(r.pct))
                        }, _toDisplayString(_ctx.sign(r.pct)) + _toDisplayString(r.pct) + "%", 3 /* TEXT, CLASS */),
                        _createTextVNode("）· MA7 " + _toDisplayString(r.ma7) + " · MA21 " + _toDisplayString(r.ma21) + " · 粘合 " + _toDisplayString(r.glue) + "% ", 1 /* TEXT */)
                      ]),
                      (r.flow)
                        ? (_openBlock(), _createElementBlock("div", _hoisted_52, [
                            _cache[17] || (_cache[17] = _createTextVNode(" 主力 ", -1 /* CACHED */)),
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
            _cache[43] || (_cache[43] = _createElementVNode("div", { class: "divider" }, null, -1 /* CACHED */)),
            _createElementVNode("details", _hoisted_53, [
              _cache[41] || (_cache[41] = _createElementVNode("summary", { class: "tiny muted" }, "口径与免责（务必读一次）", -1 /* CACHED */)),
              _createElementVNode("div", _hoisted_54, [
                (_ctx.poolMeta)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_55, [
                      _cache[20] || (_cache[20] = _createElementVNode("b", null, "候选池（三源合并）", -1 /* CACHED */)),
                      _cache[21] || (_cache[21] = _createTextVNode("：当日涨停 ", -1 /* CACHED */)),
                      _createElementVNode("b", null, _toDisplayString(_ctx.poolMeta.zt_n), 1 /* TEXT */),
                      _cache[22] || (_cache[22] = _createTextVNode(" ∪ 核心池 ", -1 /* CACHED */)),
                      _createElementVNode("b", null, _toDisplayString(_ctx.poolMeta.core_n), 1 /* TEXT */),
                      _cache[23] || (_cache[23] = _createTextVNode(" ∪ 全市场异动池 ", -1 /* CACHED */)),
                      _createElementVNode("b", null, _toDisplayString(_ctx.poolMeta.active_n), 1 /* TEXT */),
                      _cache[24] || (_cache[24] = _createTextVNode(" = ", -1 /* CACHED */)),
                      _createElementVNode("b", null, _toDisplayString(_ctx.poolMeta.total_n), 1 /* TEXT */),
                      _cache[25] || (_cache[25] = _createTextVNode(" 只。 ", -1 /* CACHED */)),
                      (_ctx.poolMeta.only_zt_effective)
                        ? (_openBlock(), _createElementBlock("span", _hoisted_56, " ⚠ 异动池本轮为空，池子退化为\"仅涨停池\"。 "))
                        : _createCommentVNode("v-if", true),
                      _createTextVNode(" 异动池口径：" + _toDisplayString(_ctx.poolMeta.criteria.min_pct) + "% ≤ 涨幅 < 涨停，且成交额 ≥ " + _toDisplayString((_ctx.poolMeta.criteria.amount_min / 1e8).toFixed(0)) + "亿，且（量比 ≥ " + _toDisplayString(_ctx.poolMeta.criteria.vol_min) + " 或 换手 ≥ " + _toDisplayString(_ctx.poolMeta.criteria.turn_min) + "%）， 按量比取前 " + _toDisplayString(_ctx.poolMeta.criteria.extra_max) + " 只。 ", 1 /* TEXT */)
                    ]))
                  : (_openBlock(), _createElementBlock("div", _hoisted_57, "候选池：当日涨停 ∪ 核心池（历史快照无池子构成信息）。")),
                (_ctx.pt.latest_bar)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_58, [
                      _cache[26] || (_cache[26] = _createElementVNode("b", null, "K线新鲜度", -1 /* CACHED */)),
                      _cache[27] || (_cache[27] = _createTextVNode("：池内最新 K 线日 ", -1 /* CACHED */)),
                      _createElementVNode("b", null, _toDisplayString(_ctx.pt.latest_bar), 1 /* TEXT */),
                      (_ctx.pt.latest_bar === _ctx.pt.date)
                        ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                            _createTextVNode("（= 快照日，正常）")
                          ], 64 /* STABLE_FRAGMENT */))
                        : (_openBlock(), _createElementBlock("span", _hoisted_59, "（≠ 快照日 " + _toDisplayString(_ctx.pt.date) + "，行情未更新）", 1 /* TEXT */)),
                      _cache[28] || (_cache[28] = _createTextVNode("； 滞后标的 ", -1 /* CACHED */)),
                      _createElementVNode("b", null, _toDisplayString(_ctx.pt.stale_n), 1 /* TEXT */),
                      _cache[29] || (_cache[29] = _createTextVNode(" 只已剔除，不产出信号（防\"旧 bar 假突破\"）。 ", -1 /* CACHED */))
                    ]))
                  : _createCommentVNode("v-if", true),
                _createElementVNode("div", null, "参数：MA" + _toDisplayString(_ctx.pt.params.ma_fast) + " / MA" + _toDisplayString(_ctx.pt.params.ma_slow) + "；粘合阈值 " + _toDisplayString((_ctx.pt.params.glue_pct * 100).toFixed(1)) + "%；持续 ≥" + _toDisplayString(_ctx.pt.params.glue_days) + " 日；放量线 " + _toDisplayString(_ctx.pt.params.vol_mult) + "×。", 1 /* TEXT */),
                _cache[38] || (_cache[38] = _createStaticVNode("<div>K线为<b>前复权</b>，按本项目惯例仅作形态判断，不与涨跌幅 / 偏离值混用。</div><div> 资金流为<b>东财口径</b>（主力净额 = 大单 + 超大单），仅加字段并<b>参与排序</b>， <b>不参与突破判定</b>（命中数不受影响）。资金分 = 当日净占比 0.5 + 近3日累计 0.3 + 连续天数 0.2， 各因子先做<b>池内百分位</b>；缺失项自动剔除并<b>重新归一</b>（行尾「N项」= 实际参与因子数）。 </div>", 2)),
                (_ctx.flowMeta && _ctx.flowMeta.srcs)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_60, [
                      _cache[30] || (_cache[30] = _createTextVNode(" 多日趋势来源分布：", -1 /* CACHED */)),
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(_ctx.flowMeta.srcs, (n, k) => {
                        return (_openBlock(), _createElementBlock("span", { key: k }, _toDisplayString(k) + "=" + _toDisplayString(n), 1 /* TEXT */))
                      }), 128 /* KEYED_FRAGMENT */)),
                      _cache[31] || (_cache[31] = _createTextVNode("。 ", -1 /* CACHED */)),
                      _cache[32] || (_cache[32] = _createElementVNode("b", null, "agg", -1 /* CACHED */)),
                      _cache[33] || (_cache[33] = _createTextVNode(" = 东财自累积（每日落一行，需连续运行数个交易日）· ", -1 /* CACHED */)),
                      _cache[34] || (_cache[34] = _createElementVNode("b", null, "sina", -1 /* CACHED */)),
                      _cache[35] || (_cache[35] = _createTextVNode(" = 新浪口径兜底（净流入额口径，绝对值与东财不可比，仅看方向/趋势）· ", -1 /* CACHED */)),
                      _cache[36] || (_cache[36] = _createElementVNode("b", null, "none", -1 /* CACHED */)),
                      _cache[37] || (_cache[37] = _createTextVNode(" = 非信号票，按需不拉取（趋势只用于信号票的排序/展示）。 ", -1 /* CACHED */))
                    ]))
                  : _createCommentVNode("v-if", true),
                _cache[39] || (_cache[39] = _createElementVNode("div", null, [
                  _createTextVNode(" 龙虎榜：当日榜（T，约 18:00 后发布，16:05/16:40 快照为空，21:00 夜间任务补算） 与前一交易日榜（T-1）"),
                  _createElementVNode("b", null, "两者都存"),
                  _createTextVNode("；上榜加标签，未上榜按常态处理。 净买/净卖为"),
                  _createElementVNode("b", null, "龙虎榜席位口径"),
                  _createTextVNode("，非全市场资金流。 ")
                ], -1 /* CACHED */)),
                (_ctx.flowMeta && _ctx.flowMeta.errors && _ctx.flowMeta.errors.length)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_61, "资金流部分失败：" + _toDisplayString(_ctx.flowMeta.errors.join('；')), 1 /* TEXT */))
                  : _createCommentVNode("v-if", true),
                (_ctx.lhbMeta && _ctx.lhbMeta.errors && _ctx.lhbMeta.errors.length)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_62, "龙虎榜部分失败：" + _toDisplayString(_ctx.lhbMeta.errors.join('；')), 1 /* TEXT */))
                  : _createCommentVNode("v-if", true),
                (_ctx.pt.flow_rows)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_63, "当日已落库资金流样本 " + _toDisplayString(_ctx.pt.flow_rows.length) + " 条（供次日算多日累计）。", 1 /* TEXT */))
                  : _createCommentVNode("v-if", true),
                (_ctx.pt.errors && _ctx.pt.errors.length)
                  ? (_openBlock(), _createElementBlock("div", _hoisted_64, "部分标的取数失败：" + _toDisplayString(_ctx.pt.errors.join('；')), 1 /* TEXT */))
                  : _createCommentVNode("v-if", true),
                _cache[40] || (_cache[40] = _createElementVNode("div", { style: {"margin-top":"4px"} }, "纯技术形态 + 资金/席位辅助，供研究参考，不构成投资建议；需与周期定位、Lab 排雷、verb 风控交叉验证后使用。", -1 /* CACHED */))
              ])
            ])
          ], 64 /* STABLE_FRAGMENT */))
    ])
  ]))
}