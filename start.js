#!/usr/bin/env node
// 用 Node 一键拉起 github-xhs-automation 后端（脱离终端常驻）
// 用法：
//   node start.js          启动（已运行则提示，不重复拉）
//   node start.js stop     停止
//   node start.js status   查看状态
const { spawn } = require('child_process');
const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 8787;
const PY = process.env.PY || '/Users/lhl/.workbuddy/binaries/python/versions/3.13.12/bin/python3';
const DIR = __dirname;
const PID_FILE = path.join(DIR, 'server.pid');
const LOG = path.join(DIR, 'server.log');
const URL = `http://127.0.0.1:${PORT}/console.html`;

function probe(cb) {
  const req = http.get({ host: '127.0.0.1', port: PORT, path: '/api/overview', timeout: 1500 },
    (res) => { res.resume(); cb(true); });
  req.on('error', () => cb(false));
  req.on('timeout', () => { req.destroy(); cb(false); });
}

function stop() {
  let pid;
  try { pid = parseInt(fs.readFileSync(PID_FILE, 'utf8')); } catch (e) {}
  if (pid) {
    try { process.kill(pid, 'SIGTERM'); console.log(`已停止后端进程 pid ${pid}`); }
    catch (e) { console.log('进程已不在，无需停止'); }
  } else {
    console.log('未找到 pid 文件，可能未用本脚本启动');
  }
  try { fs.unlinkSync(PID_FILE); } catch (e) {}
}

function start() {
  probe((up) => {
    if (up) {
      console.log(`✅ 服务已在运行：${URL}`);
      process.exit(0);
    }
    const out = fs.openSync(LOG, 'a');
    const p = spawn(PY, ['server.py'], {
      cwd: DIR,
      detached: true,
      stdio: ['ignore', out, out],
      env: process.env,
    });
    fs.writeFileSync(PID_FILE, String(p.pid));
    p.unref();
    let tries = 0;
    const iv = setInterval(() => {
      probe((u) => {
        if (u) {
          clearInterval(iv);
          console.log(`✅ 已用 Node 拉起后端（python pid ${p.pid}）：${URL}`);
          process.exit(0);
        }
        if (++tries > 30) {
          clearInterval(iv);
          console.log('⚠️ 启动超时，请查看 server.log');
          process.exit(1);
        }
      });
    }, 500);
  });
}

const cmd = process.argv[2];
if (cmd === 'stop') stop();
else if (cmd === 'status') probe((u) => { console.log(u ? `✅ 运行中：${URL}` : '⭕ 未运行'); process.exit(0); });
else start();
