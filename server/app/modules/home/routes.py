# -*- coding: utf-8 -*-
"""
首页路由（开发调试台）
用途：在浏览器中直接可视化的调用后端接口，便于开发/验收时"看效果"。
仅用于开发环境，不含任何业务逻辑。
"""
from flask import Blueprint, Response

home_bp = Blueprint('home', __name__)

PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>衣笺小札 · 接口调试台</title>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
         background: #f4f7fb; color: #2b3441; }
  header { background: linear-gradient(135deg, #8fb3d9, #a9c4e0); color: #fff;
           padding: 26px 32px; }
  header h1 { margin: 0 0 6px; font-size: 22px; font-weight: 600; letter-spacing: 1px; }
  header p { margin: 0; font-size: 13px; opacity: .9; }
  .wrap { max-width: 1080px; margin: 0 auto; padding: 22px 20px 60px; display: grid;
          grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 18px; }
  .card { background: #fff; border-radius: 12px; padding: 18px 20px;
          box-shadow: 0 2px 10px rgba(143,179,217,.15); }
  .card h2 { margin: 0 0 14px; font-size: 15px; color: #3d5a80; font-weight: 600;
             border-left: 3px solid #8fb3d9; padding-left: 9px; }
  label { display: block; font-size: 12px; color: #7b8794; margin: 8px 0 4px; }
  input, select { width: 100%; padding: 8px 10px; border: 1px solid #d7e0ea; border-radius: 7px;
                  font-size: 13px; outline: none; background: #fbfcfe; }
  input:focus, select:focus { border-color: #8fb3d9; }
  button { margin-top: 10px; padding: 8px 16px; border: none; border-radius: 7px;
           background: #8fb3d9; color: #fff; font-size: 13px; cursor: pointer;
           transition: .15s; }
  button:hover { background: #7aa2cc; }
  button.ghost { background: #eef3f9; color: #3d5a80; }
  .row { display: flex; gap: 10px; }
  .row > * { flex: 1; }
  #token-box { font-size: 12px; color: #5b7; word-break: break-all; margin-top: 8px;
               background: #f1f8f2; padding: 8px; border-radius: 6px; display: none; }
  #log { background: #1e2733; color: #d6e2ef; border-radius: 12px; padding: 16px;
         font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 12px;
         line-height: 1.6; white-space: pre-wrap; word-break: break-all;
         max-height: 460px; overflow: auto; }
  .full { grid-column: 1 / -1; }
  .log-title { color: #9fb3c8; margin: 0 0 10px; font-size: 14px; }
</style>
</head>
<body>
<header>
  <h1>衣笺小札 · 后端接口调试台</h1>
  <p>直接在浏览器中调用后端接口 —— 注册 / 登录 / 衣物管理（开发调试用）</p>
</header>

<div class="wrap">
  <div class="card">
    <h2>服务状态</h2>
    <button class="ghost" onclick="ping()">测试 ping</button>
    <button class="ghost" onclick="dbCheck()">测试数据库</button>
  </div>

  <div class="card">
    <h2>用户</h2>
    <label>用户名</label><input id="u" value="testuser">
    <label>邮箱</label><input id="e" value="test@example.com">
    <label>密码</label><input id="p" type="password" value="123456">
    <div class="row">
      <button onclick="register()">注册</button>
      <button onclick="login()">登录</button>
    </div>
    <div id="token-box"></div>
  </div>

  <div class="card">
    <h2>添加衣物</h2>
    <label>图片 URL</label><input id="image_url" value="https://picsum.photos/400">
    <div class="row">
      <div>
        <label>类型</label>
        <select id="type">
          <option>上装</option><option>下装</option><option>外套</option>
          <option>鞋子</option><option>配饰</option>
        </select>
      </div>
      <div>
        <label>颜色</label><input id="color" value="黑色">
      </div>
      <div>
        <label>季节</label>
        <select id="season"><option>春</option><option>夏</option><option>秋</option>
          <option>冬</option><option>全季</option></select>
      </div>
    </div>
    <button onclick="addItem()">添加衣物</button>
  </div>

  <div class="card">
    <h2>衣物查询</h2>
    <div class="row">
      <div><label>类型筛选</label><input id="f_type" placeholder="如：外套"></div>
      <div><label>颜色筛选</label><input id="f_color" placeholder="如：黑色"></div>
      <div><label>季节筛选</label><input id="f_season" placeholder="如：冬"></div>
    </div>
    <div class="row">
      <div><label>页码</label><input id="f_page" value="1"></div>
      <div><label>每页条数</label><input id="f_per" value="10"></div>
    </div>
    <button onclick="listItems()">查询列表</button>
    <label>衣物 ID（详情/更新/删除）</label>
    <input id="item_id" value="1">
    <div class="row">
      <button class="ghost" onclick="getItem()">详情</button>
      <button class="ghost" onclick="updateItem()">更新状态</button>
      <button class="ghost" onclick="deleteItem()">软删除</button>
    </div>
  </div>

  <div class="card full">
    <p class="log-title">响应结果</p>
    <div id="log">等待操作...</div>
  </div>
</div>

<script>
const BASE = '';
let TOKEN = '';

function show(title, data) {
  const el = document.getElementById('log');
  el.textContent = '▶ ' + title + '\\n' + JSON.stringify(data, null, 2);
}
function showErr(e) { show('请求失败', { error: String(e) }); }

async function call(method, path, body, auth) {
  const headers = { 'Content-Type': 'application/json' };
  if (auth && TOKEN) headers['Authorization'] = 'Bearer ' + TOKEN;
  const res = await fetch(BASE + path, {
    method, headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  return res.json();
}

async function ping() { try { show('GET /api/v1/test/ping', await call('GET', '/api/v1/test/ping')); } catch (e) { showErr(e); } }
async function dbCheck() { try { show('GET /api/v1/test/db', await call('GET', '/api/v1/test/db')); } catch (e) { showErr(e); } }

async function register() {
  try {
    const r = await call('POST', '/api/auth/register', {
      username: u.value.trim(), email: e.value.trim(), password: p.value,
    });
    show('POST /api/auth/register', r);
  } catch (err) { showErr(err); }
}

async function login() {
  try {
    const r = await call('POST', '/api/auth/login', { account: u.value.trim(), password: p.value });
    if (r.code === 0) {
      TOKEN = r.data.access_token;
      const box = document.getElementById('token-box');
      box.style.display = 'block';
      box.textContent = '已登录，Token 已保存（' + TOKEN.slice(0, 24) + '...）';
    }
    show('POST /api/auth/login', r);
  } catch (err) { showErr(err); }
}

async function addItem() {
  try {
    const r = await call('POST', '/api/items', {
      image_url: image_url.value.trim(), type: type.value,
      color: color.value.trim(), season: season.value,
    }, true);
    show('POST /api/items', r);
  } catch (err) { showErr(err); }
}

async function listItems() {
  try {
    const qs = new URLSearchParams();
    if (f_type.value.trim()) qs.set('type', f_type.value.trim());
    if (f_color.value.trim()) qs.set('color', f_color.value.trim());
    if (f_season.value.trim()) qs.set('season', f_season.value.trim());
    qs.set('page', f_page.value || 1);
    qs.set('per_page', f_per.value || 10);
    const r = await call('GET', '/api/items?' + qs.toString(), null, true);
    show('GET /api/items?' + qs.toString(), r);
  } catch (err) { showErr(err); }
}

async function getItem() {
  try { show('GET /api/items/' + item_id.value, await call('GET', '/api/items/' + item_id.value, null, true)); }
  catch (err) { showErr(err); }
}

async function updateItem() {
  try {
    show('PUT /api/items/' + item_id.value, await call('PUT', '/api/items/' + item_id.value,
      { status: '洗衣中' }, true));
  } catch (err) { showErr(err); }
}

async function deleteItem() {
  try { show('DELETE /api/items/' + item_id.value, await call('DELETE', '/api/items/' + item_id.value, null, true)); }
  catch (err) { showErr(err); }
}
</script>
</body>
</html>
"""


@home_bp.get('/')
def index():
    """浏览器首页：接口调试台"""
    return Response(PAGE, mimetype='text/html; charset=utf-8')
