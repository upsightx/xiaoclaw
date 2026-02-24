#!/bin/bash
# xiaoclaw Docker 并发压力测试
# 用法: bash tests/docker_stress.sh [并发数, 默认3]

set -e
CONCURRENCY=${1:-3}
IMAGE="xiaoclaw:test"
PASS=0
FAIL=0
DIR="/tmp/xc-stress-$$"
mkdir -p "$DIR"

ENV_ARGS="-e OPENAI_API_KEY=sk-iHus2xPomk0gCRPcqhxbLOw8zffMUeg7pryj1qnO5Cb698pW -e OPENAI_BASE_URL=https://ai.ltcraft.cn:12000/v1 -e XIAOCLAW_MODEL=claude-opus-4-6"

echo "🐾 xiaoclaw Docker 并发压力测试"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "并发: $CONCURRENCY | 镜像: $IMAGE"
echo ""

# 生成测试脚本
cat > "$DIR/t1.py" << 'EOF'
import asyncio, sys, time
from xiaoclaw.core import XiaClaw, XiaClawConfig
async def run():
    t=time.time(); claw=XiaClaw(XiaClawConfig.from_env())
    r=await claw.handle_message('你是谁')
    ok='xiaoclaw' in r.lower()
    print(f'{"✅" if ok else "❌"} 身份: {r[:60]}  ⏱{time.time()-t:.1f}s')
    sys.exit(0 if ok else 1)
asyncio.run(run())
EOF

cat > "$DIR/t2.py" << 'EOF'
import asyncio, sys, time
from xiaoclaw.core import XiaClaw, XiaClawConfig
async def run():
    t=time.time(); claw=XiaClaw(XiaClawConfig.from_env())
    await claw.handle_message('创建文件 /tmp/t.txt 内容是 test123')
    r=await claw.handle_message('读取 /tmp/t.txt')
    ok='test123' in r
    print(f'{"✅" if ok else "❌"} 文件读写: {r[:60]}  ⏱{time.time()-t:.1f}s')
    sys.exit(0 if ok else 1)
asyncio.run(run())
EOF

cat > "$DIR/t3.py" << 'EOF'
import asyncio, sys, time
from xiaoclaw.core import XiaClaw, XiaClawConfig
async def run():
    t=time.time(); claw=XiaClaw(XiaClawConfig.from_env())
    await claw.handle_message('我的名字叫张三')
    r=await claw.handle_message('我叫什么名字')
    ok='张三' in r
    print(f'{"✅" if ok else "❌"} 多轮记忆: {r[:60]}  ⏱{time.time()-t:.1f}s')
    sys.exit(0 if ok else 1)
asyncio.run(run())
EOF

cat > "$DIR/t4.py" << 'EOF'
import asyncio, sys, time
from xiaoclaw.core import XiaClaw, XiaClawConfig
async def run():
    t=time.time(); claw=XiaClaw(XiaClawConfig.from_env())
    r=await claw.handle_message('搜索一下Python最新版本是什么')
    ok=len(r)>20 and 'Error' not in r[:20]
    print(f'{"✅" if ok else "❌"} Web搜索: {r[:80]}  ⏱{time.time()-t:.1f}s')
    sys.exit(0 if ok else 1)
asyncio.run(run())
EOF

cat > "$DIR/t5.py" << 'EOF'
import asyncio, sys, time
from xiaoclaw.core import XiaClaw, XiaClawConfig
async def run():
    t=time.time(); claw=XiaClaw(XiaClawConfig.from_env())
    r=await claw.handle_message('读取 /tmp/这个文件绝对不存在.txt')
    ok=len(r)>5
    print(f'{"✅" if ok else "❌"} 错误恢复: {r[:60]}  ⏱{time.time()-t:.1f}s')
    sys.exit(0 if ok else 1)
asyncio.run(run())
EOF

cat > "$DIR/t6.py" << 'EOF'
import asyncio, sys, time
from xiaoclaw.core import XiaClaw, XiaClawConfig
async def run():
    t=time.time(); claw=XiaClaw(XiaClawConfig.from_env())
    r=await claw.handle_message('用三句话介绍人工智能')
    ok=len(r)>30
    print(f'{"✅" if ok else "❌"} 中文生成({len(r)}字): {r[:60]}  ⏱{time.time()-t:.1f}s')
    sys.exit(0 if ok else 1)
asyncio.run(run())
EOF

cat > "$DIR/t7.py" << 'EOF'
import asyncio, sys, time
from xiaoclaw.core import XiaClaw, XiaClawConfig
async def run():
    t=time.time(); claw=XiaClaw(XiaClawConfig.from_env())
    r=await claw.handle_message('计算 123 * 456 + 789')
    ok='56877' in r or '56,877' in r
    print(f'{"✅" if ok else "❌"} 计算: {r[:60]}  ⏱{time.time()-t:.1f}s')
    sys.exit(0 if ok else 1)
asyncio.run(run())
EOF

cat > "$DIR/t8.py" << 'EOF'
import asyncio, sys, time
from xiaoclaw.core import XiaClaw, XiaClawConfig
async def run():
    t=time.time(); claw=XiaClaw(XiaClawConfig.from_env())
    for i,m in enumerate(['你好','1+1等于几','刚才等于几','你是谁','今天聊了几轮'],1):
        r=await claw.handle_message(m)
        if not r or len(r)<2:
            print(f'❌ 第{i}轮空回复  ⏱{time.time()-t:.1f}s'); sys.exit(1)
    print(f'✅ 5轮对话全部正常  ⏱{time.time()-t:.1f}s')
asyncio.run(run())
EOF

cat > "$DIR/t9.py" << 'EOF'
import asyncio, sys, time
from xiaoclaw.core import XiaClaw, XiaClawConfig
async def run():
    t=time.time(); claw=XiaClaw(XiaClawConfig.from_env())
    chunks=[]
    async for c in claw.handle_message_stream('写一句关于AI的话'):
        chunks.append(c)
    text=''.join(chunks)
    ok=len(text)>5
    print(f'{"✅" if ok else "❌"} Stream: {len(chunks)}chunks {text[:60]}  ⏱{time.time()-t:.1f}s')
    sys.exit(0 if ok else 1)
asyncio.run(run())
EOF

cat > "$DIR/t10.py" << 'EOF'
import asyncio, sys, time
from xiaoclaw.core import XiaClaw, XiaClawConfig
async def run():
    t=time.time(); claw=XiaClaw(XiaClawConfig.from_env())
    r=await claw.handle_message('帮我在/tmp创建hello.txt写入hello和world.txt写入world')
    r2=await claw.handle_message('列出/tmp目录有哪些文件')
    ok='hello' in r2 or 'world' in r2 or 'txt' in r2
    print(f'{"✅" if ok else "❌"} 多工具: {r2[:60]}  ⏱{time.time()-t:.1f}s')
    sys.exit(0 if ok else 1)
asyncio.run(run())
EOF

TESTS=(t1 t2 t3 t4 t5 t6 t7 t8 t9 t10)
NAMES=("身份识别" "文件读写" "多轮记忆" "Web搜索" "错误恢复" "中文生成" "计算能力" "5轮对话" "Stream" "多工具")
NUM=${#TESTS[@]}

echo "测试: $NUM 个 | 开始时间: $(date '+%H:%M:%S')"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

START=$(date +%s)
PIDS=()
IDX=()
RUNNING=0
NEXT=0

while [ $NEXT -lt $NUM ] || [ $RUNNING -gt 0 ]; do
    while [ $RUNNING -lt $CONCURRENCY ] && [ $NEXT -lt $NUM ]; do
        i=$NEXT
        (
            docker run --rm --memory=128m $ENV_ARGS \
                -v "$DIR/${TESTS[$i]}.py:/test.py:ro" \
                "$IMAGE" python3 /test.py > "$DIR/${TESTS[$i]}.out" 2>&1
            echo $? > "$DIR/${TESTS[$i]}.rc"
        ) &
        PIDS+=($!)
        IDX+=($i)
        RUNNING=$((RUNNING+1))
        NEXT=$((NEXT+1))
    done

    # 等一个完成
    sleep 2
    NEW_PIDS=()
    NEW_IDX=()
    for j in "${!PIDS[@]}"; do
        if kill -0 "${PIDS[$j]}" 2>/dev/null; then
            NEW_PIDS+=("${PIDS[$j]}")
            NEW_IDX+=("${IDX[$j]}")
        else
            i=${IDX[$j]}
            rc=$(cat "$DIR/${TESTS[$i]}.rc" 2>/dev/null || echo 1)
            out=$(cat "$DIR/${TESTS[$i]}.out" 2>/dev/null | tail -1)
            if [ "$rc" = "0" ]; then
                PASS=$((PASS+1))
            else
                FAIL=$((FAIL+1))
                echo "   ⚠ ${NAMES[$i]}: $out"
            fi
            echo "   [$((PASS+FAIL))/$NUM] $out"
            RUNNING=$((RUNNING-1))
        fi
    done
    PIDS=("${NEW_PIDS[@]}")
    IDX=("${NEW_IDX[@]}")
done

END=$(date +%s)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 结果: ✅ $PASS / ❌ $FAIL / 共 $NUM"
echo "⏱ 总耗时: $((END-START))s | 并发: $CONCURRENCY"
free -h | grep Mem | awk '{print "💾 内存: 总"$2" 用"$3" 余"$7}'

if [ $FAIL -gt 0 ]; then
    echo ""
    echo "失败详情:"
    for i in "${!TESTS[@]}"; do
        rc=$(cat "$DIR/${TESTS[$i]}.rc" 2>/dev/null || echo 1)
        if [ "$rc" != "0" ]; then
            echo "  ── ${NAMES[$i]} ──"
            cat "$DIR/${TESTS[$i]}.out" 2>/dev/null | tail -5 | sed 's/^/  /'
        fi
    done
fi

echo ""
[ $FAIL -eq 0 ] && echo "🎉 全部通过！" || echo "⚠ 有 $FAIL 个失败"
