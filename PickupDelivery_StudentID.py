import csv
import sys
import time

TIME_LIMIT = 300    # seconds. Algorithm 2 must finish within this limit (measured by the TA).


class Order:
    def __init__(self, order_id, order_time, prep_time, volume, deadline):
        self.order_id = order_id
        self.order_time = order_time
        self.prep_time = prep_time
        self.volume = volume
        self.deadline = deadline
        self.ready_time = order_time + prep_time


class Rider:
    def __init__(self, rider_type, speed, capacity, variable_cost, fixed_cost, available):
        self.rider_type = rider_type
        self.speed = speed
        self.capacity = capacity
        self.variable_cost = variable_cost
        self.fixed_cost = fixed_cost
        self.available = available


class Bundle:
    def __init__(self, bundle_id, pickups, deliveries):
        self.bundle_id = bundle_id
        self.pickups = pickups          # list of order IDs in pickup order
        self.deliveries = deliveries    # list of order IDs in delivery order
        self.rider_type = None
        self.cost = None


class PickupDelivery:
    def __init__(self, orders, riders, dist):
        self.orders = orders
        self.riders = riders
        self.dist = dist

    def solve_savings(self):
        # TODO: return (bundles, merges)
        #   bundles: list of Bundle with rider_type assigned
        #   merges : list of the merged bundles' order IDs, in merge order
        n = len(self.orders)
        dist = self.dist
        riders = {}                                 # 타입 이름 -> Rider
        for r in self.riders:
            riders[r.rider_type] = r
        car, bike = riders['CAR'], riders['BIKE']
        ready = [o.ready_time for o in self.orders]
        deadline = [o.deadline for o in self.orders]
        volume = [o.volume for o in self.orders]
        # 타입별 이동시간 행렬: round(distance / speed) (파이썬 내장 round)
        ttime = {}
        for name in riders:
            ttime[name] = [[round(d / riders[name].speed) for d in row] for row in dist]

        def route_check(pickups, deliveries, rider):
            """경로가 실행 가능하면 이동거리, 불가능하면 None"""
            if sum(volume[o] for o in pickups) > rider.capacity:     # 용량 제약
                return None
            T = ttime[rider.rider_type]
            prev = pickups[0]
            t = ready[prev]                 # 첫 픽업 장소를 ready time에 출발
            d = 0
            for o in pickups[1:]:
                t += T[prev][o]
                d += dist[prev][o]
                if t < ready[o]:            # 일찍 도착하면 ready time까지 대기
                    t = ready[o]
                prev = o
            for o in deliveries:            # 픽업을 모두 끝낸 뒤 배달
                t += T[prev][o + n]
                d += dist[prev][o + n]
                if t > deadline[o]:         # 마감시간 위반
                    return None
                prev = o + n
            return d

        def type_costs(pickups, deliveries):
            """(CAR 비용, BIKE 비용). 불가능한 타입은 None. 비용 = 고정비 + 100m당 변동비"""
            dc = route_check(pickups, deliveries, car)
            db = route_check(pickups, deliveries, bike)
            cc = None if dc is None else car.fixed_cost + car.variable_cost * dc / 100
            cb = None if db is None else bike.fixed_cost + bike.variable_cost * db / 100
            return cc, cb

        def cheaper(cc, cb):
            """가능한 타입 중 더 싼 비용 (BIKE 대수 제한은 무시)"""
            if cb is None:
                return cc
            if cc is None:
                return cb
            return min(cc, cb)

        def best_merge(A, B):
            """A, B를 합치는 4가지 후보 중 가장 싼 것 (CAR로 불가능한 후보 제외)"""
            if A['vol'] + B['vol'] > car.capacity:
                return None
            pa, pb, da, db = A['p'], B['p'], A['d'], B['d']
            # 리스트 순서 = 과제에서 정한 동점 처리 순서
            candidates = [(pa + pb, da + db), (pa + pb, db + da), (pb + pa, da + db), (pb + pa, db + da)]
            best = None
            for ps, ds in candidates:
                cc, cb = type_costs(ps, ds)
                if cc is None:                      # CAR로 불가능하면 허용 안 함
                    continue
                c = cheaper(cc, cb)
                if best is None or c < best[0]:     # 동점이면 앞의 후보 유지
                    best = (c, ps, ds)
            return best

        def update_saving(a, b):
            """번들 쌍 (a, b)의 saving을 계산해서 양수일 때만 저장"""
            res = best_merge(bund[a], bund[b])
            if res is None:
                return
            saving = round(bund[a]['cost'] + bund[b]['cost'] - res[0], 2)
            if saving > 0:
                savings[(a, b)] = (saving, res)

        # A. 초기: 주문 하나당 번들 하나 (번들 ID = 가장 작은 주문 ID)
        bund = {}
        for i in range(n):
            cc, cb = type_costs([i], [i])
            bund[i] = {'p': [i], 'd': [i], 'vol': volume[i], 'cost': cheaper(cc, cb)}

        # B. 모든 쌍 (A의 ID < B의 ID)의 saving 계산
        savings = {}
        for a in range(n):
            for b in range(a + 1, n):
                update_saving(a, b)

        merges = []
        while savings:
            # C. saving이 가장 큰 쌍 선택 (동점이면 A의 ID, 그다음 B의 ID가 작은 쌍)
            best_key = None
            best_s = None
            for key in savings:
                s = savings[key][0]
                if best_key is None or s > best_s or (s == best_s and key < best_key):
                    best_key, best_s = key, s
            a, b = best_key
            cost, ps, ds = savings[best_key][1]
            # 병합: 새 번들의 ID는 더 작은 ID인 a
            bund[a] = {'p': ps, 'd': ds, 'vol': bund[a]['vol'] + bund[b]['vol'], 'cost': cost}
            del bund[b]
            merges.append(sorted(ps))
            # D. a 또는 b가 들어간 쌍은 지우고, 새 번들 a와의 saving만 다시 계산
            for key in list(savings.keys()):
                if a in key or b in key:
                    del savings[key]
            for x in bund:
                if x != a:
                    update_saving(min(a, x), max(a, x))

        # E. 라이더 배정: BIKE가 더 싼 번들에 (CAR 비용 - BIKE 비용)이 큰 순서로 (동점이면 작은 ID)
        bundles = []
        cand = []
        costs = {}
        for bid in sorted(bund):
            b = Bundle(bid, bund[bid]['p'], bund[bid]['d'])
            bundles.append(b)
            cc, cb = type_costs(b.pickups, b.deliveries)
            costs[bid] = (cc, cb)
            if cb is not None and (cc is None or cb < cc):
                diff = float('inf') if cc is None else round(cc - cb, 2)
                cand.append((-diff, bid))
        cand.sort()
        bike_ids = [bid for _, bid in cand[:bike.available]]
        for b in bundles:
            cc, cb = costs[b.bundle_id]
            if b.bundle_id in bike_ids:
                b.rider_type, b.cost = 'BIKE', cb
            else:
                b.rider_type, b.cost = 'CAR', cc
        return bundles, merges

    def solve_my(self):
        # TODO: return (bundles, []). The merge_step block is not written for My Algorithm.
        # My Algorithm: Savings 해에서 출발하는 지역 탐색 + 흔들기
        #   1) 개선: 합치기 / 주문 이동 / 주문 교환 중 총비용이 줄어드는 것을 계속 적용
        #   2) 흔들기: 더 이상 좋아지지 않으면 가까운 번들 몇 개를 1개짜리로 풀고 다시 1)
        #   3) 시간이 끝나면 가장 좋았던 해에 라이더를 배정해서 반환
        start = time.perf_counter()
        end_time = start + TIME_LIMIT - 40      # 40초 여유를 두고 종료
        n = len(self.orders)
        dist = self.dist
        riders = {}
        for r in self.riders:
            riders[r.rider_type] = r
        car, bike = riders['CAR'], riders['BIKE']
        ready = [o.ready_time for o in self.orders]
        deadline = [o.deadline for o in self.orders]
        volume = [o.volume for o in self.orders]
        # 타입별 이동시간 행렬: round(distance / speed)
        ttime = {}
        for name in riders:
            ttime[name] = [[round(d / riders[name].speed) for d in row] for row in dist]

        def route_check(pickups, deliveries, rider):
            """경로가 실행 가능하면 이동거리, 불가능하면 None"""
            if sum(volume[o] for o in pickups) > rider.capacity:
                return None
            T = ttime[rider.rider_type]
            prev = pickups[0]
            t = ready[prev]                     # 첫 픽업 장소를 ready time에 출발
            d = 0
            for o in pickups[1:]:
                t += T[prev][o]
                d += dist[prev][o]
                if t < ready[o]:                # 일찍 도착하면 대기
                    t = ready[o]
                prev = o
            for o in deliveries:
                t += T[prev][o + n]
                d += dist[prev][o + n]
                if t > deadline[o]:             # 마감시간 위반
                    return None
                prev = o + n
            return d

        def make(pickups, deliveries):
            """번들(딕셔너리) 생성: 경로와 CAR/BIKE 비용 (불가능한 타입은 None). 둘 다 불가능하면 None"""
            dc = route_check(pickups, deliveries, car)
            db = route_check(pickups, deliveries, bike)
            if dc is None and db is None:
                return None
            cc = None if dc is None else car.fixed_cost + car.variable_cost * dc / 100
            cb = None if db is None else bike.fixed_cost + bike.variable_cost * db / 100
            return {'p': pickups, 'd': deliveries, 'cc': cc, 'cb': cb}

        def score(b):
            """경로 비교용 비용: 가능한 타입 중 더 싼 비용"""
            if b['cc'] is None:
                return b['cb']
            if b['cb'] is not None and b['cb'] < b['cc']:
                return b['cb']
            return b['cc']

        def total_cost(sol):
            """해의 총비용: CAR로 불가능한 번들은 무조건 BIKE.
            나머지는 CAR라고 보고, BIKE로 바꾸면 이득인 번들을 이득이 큰 순서로 남은 BIKE 대수만큼 바꾼다"""
            total = 0
            need_bike = 0
            gains = []
            for b in sol:
                if b['cc'] is None:
                    total += b['cb']
                    need_bike += 1
                else:
                    total += b['cc']
                    if b['cb'] is not None and b['cb'] < b['cc']:
                        gains.append(b['cc'] - b['cb'])
            left = bike.available - need_bike
            if left < 0:                            # BIKE가 모자라면 불가능한 해
                return float('inf')
            gains.sort(reverse=True)
            return total - sum(gains[:left])

        insert_memo = {}                            # (번들 경로, 주문) -> best_insert 결과 저장

        def best_insert(b, i):
            """번들 b에 주문 i를 넣는 가장 싼 방법 (픽업 위치 x 배달 위치 모두 시도)"""
            if b is None:
                return make([i], [i])
            key = (tuple(b['p']), tuple(b['d']), i)
            if key in insert_memo:                  # 이미 계산한 적 있으면 저장된 결과 사용
                return insert_memo[key]
            if len(insert_memo) > 2000000:          # 메모리 보호
                insert_memo.clear()
            best = None
            for pi in range(len(b['p']) + 1):
                pickups = b['p'][:pi] + [i] + b['p'][pi:]
                for di in range(len(b['d']) + 1):
                    deliveries = b['d'][:di] + [i] + b['d'][di:]
                    cand = make(pickups, deliveries)
                    if cand is not None and (best is None or score(cand) < score(best)):
                        best = cand
            insert_memo[key] = best
            return best

        def remove(b, i):
            """번들 b에서 주문 i를 뺀 번들. 비면 None, 빼서 불가능해지면 False"""
            pickups = [o for o in b['p'] if o != i]
            if not pickups:
                return None
            deliveries = [o for o in b['d'] if o != i]
            cand = make(pickups, deliveries)
            return False if cand is None else cand

        def merge(a, b):
            """두 번들을 합치는 가장 싼 방법:
            Savings처럼 앞뒤로 붙이는 4가지 + b의 주문을 a에 하나씩 끼워 넣는 방법"""
            cands = [make(a['p'] + b['p'], a['d'] + b['d']), make(a['p'] + b['p'], b['d'] + a['d']),
                     make(b['p'] + a['p'], a['d'] + b['d']), make(b['p'] + a['p'], b['d'] + a['d'])]
            cur = a
            for o in b['p']:
                cur = best_insert(cur, o)
                if cur is None:
                    break
            cands.append(cur)
            best = None
            for c in cands:
                if c is not None and (best is None or score(c) < score(best)):
                    best = c
            return best

        # 가까운 주문 목록: 픽업 거리 + 배달 거리 + 준비시각 차이(거리로 환산)가 작은 10개
        near = []
        for i in range(n):
            order = []
            for j in range(n):
                if j != i:
                    gap = dist[i][j] + dist[i + n][j + n] + abs(ready[i] - ready[j]) * car.speed
                    order.append((gap, j))
            order.sort()
            near.append([j for _, j in order[:10]])

        def where(sol):
            """주문 -> 그 주문이 들어 있는 번들의 위치(인덱스)"""
            pos = [0] * n
            for k in range(len(sol)):
                for o in sol[k]['p']:
                    pos[o] = k
            return pos

        def replace(sol, old_idx, new_bundles):
            """sol에서 old_idx 위치의 번들을 지우고 new_bundles(None 제외)를 추가한 새 해"""
            new = [sol[k] for k in range(len(sol)) if k not in old_idx]
            for b in new_bundles:
                if b is not None:
                    new.append(b)
            return new

        def merge_pass(sol, cur):
            """합치기: 총비용이 줄어드는 두 번들을 찾으면 합친다"""
            for a in range(len(sol)):
                for b in range(a + 1, len(sol)):
                    if time.perf_counter() > end_time:
                        return None
                    m = merge(sol[a], sol[b])
                    if m is None:
                        continue
                    new = replace(sol, [a, b], [m])
                    c = total_cost(new)
                    if c < cur - 1e-6:
                        return new, c
            return None

        def move_pass(sol, cur):
            """주문 이동: 주문 i를 가까운 주문이 있는 번들 / 자기 번들의 다른 위치 / 혼자 배달로 옮긴다"""
            pos = where(sol)
            for i in range(n):
                if time.perf_counter() > end_time:
                    return None
                a = pos[i]
                rest = remove(sol[a], i)
                if rest is False:
                    continue
                targets = [a]                           # 자기 번들 안에서 위치 바꾸기
                for j in near[i]:
                    if pos[j] not in targets:
                        targets.append(pos[j])
                for b in targets:
                    if b == a:
                        new = replace(sol, [a], [best_insert(rest, i)])
                    else:
                        nb = best_insert(sol[b], i)
                        if nb is None:
                            continue
                        new = replace(sol, [a, b], [rest, nb])
                    c = total_cost(new)
                    if c < cur - 1e-6:
                        return new, c
                if rest is not None:                    # 혼자 배달하는 번들로 분리
                    new = replace(sol, [a], [rest, make([i], [i])])
                    c = total_cost(new)
                    if c < cur - 1e-6:
                        return new, c
            return None

        def swap_pass(sol, cur):
            """교환: 서로 다른 번들에 있는 가까운 두 주문 i, j를 맞바꾼다"""
            pos = where(sol)
            for i in range(n):
                if time.perf_counter() > end_time:
                    return None
                for j in near[i]:
                    a, b = pos[i], pos[j]
                    if a == b:
                        continue
                    ra = remove(sol[a], i)
                    rb = remove(sol[b], j)
                    if ra is False or rb is False:
                        continue
                    na = best_insert(ra, j)
                    nb = best_insert(rb, i)
                    if na is None or nb is None:
                        continue
                    new = replace(sol, [a, b], [na, nb])
                    c = total_cost(new)
                    if c < cur - 1e-6:
                        return new, c
            return None

        def local_search(sol):
            """합치기 -> 이동 -> 교환을 더 이상 좋아지지 않을 때까지 반복"""
            cur = total_cost(sol)
            while time.perf_counter() < end_time:
                res = merge_pass(sol, cur)
                if res is None:
                    res = move_pass(sol, cur)
                if res is None:
                    res = swap_pass(sol, cur)
                if res is None:                         # 세 방법 모두 개선 실패 -> 지역 최적
                    break
                sol, cur = res
            return sol, cur

        # 난수 (선형 합동법): 흔들 번들을 고를 때 사용
        seed = [2026]

        def rand_int(k):
            """0 이상 k 미만의 정수 난수"""
            seed[0] = (seed[0] * 1103515245 + 12345) % 2147483648
            return (seed[0] // 65536) % k

        def perturb(sol):
            """흔들기: 무작위 주문 하나와 가까운 주문들이 속한 번들(2~4개)을 1개짜리로 푼다"""
            pos = where(sol)
            i = rand_int(n)
            size = 2 + rand_int(3)
            chosen = [pos[i]]
            for j in near[i]:
                if len(chosen) >= size:
                    break
                if pos[j] not in chosen:
                    chosen.append(pos[j])
            singles = []
            for k in chosen:
                for o in sol[k]['p']:
                    singles.append(make([o], [o]))
            return replace(sol, chosen, singles)

        # 1) 초기해 = Savings 해
        sav_bundles, _ = self.solve_savings()
        sol = []
        for b in sav_bundles:
            sol.append(make(list(b.pickups), list(b.deliveries)))
        sol, cur = local_search(sol)
        best, best_cost = sol, cur

        # 2) 흔들기 + 지역 탐색 반복
        #    새 해가 최고 기록보다 1% 이내로만 나쁘면 현재 해로 받아들이고(다른 곳도 탐색),
        #    그보다 나쁘면 최고 기록 해로 돌아간다
        while time.perf_counter() < end_time:
            new, new_cost = local_search(perturb(sol))
            if new_cost < best_cost - 1e-6:
                best, best_cost = new, new_cost
            if new_cost <= best_cost * 1.01:
                sol, cur = new, new_cost
            else:
                sol, cur = best, best_cost

        # 3) 라이더 배정 (Savings의 E 단계와 같은 규칙) 후 Bundle로 변환
        result = []
        for b in best:
            result.append(Bundle(min(b['p']), b['p'], b['d']))
        result.sort(key=lambda x: x.bundle_id)
        info = {}
        forced = []                                     # CAR로 불가능 -> 반드시 BIKE
        cand = []
        for b in best:
            bid = min(b['p'])
            info[bid] = b
            if b['cc'] is None:
                forced.append(bid)
            elif b['cb'] is not None and b['cb'] < b['cc']:
                cand.append((-(b['cc'] - b['cb']), bid))
        cand.sort()
        bike_ids = forced + [bid for _, bid in cand[:bike.available - len(forced)]]
        for b in result:
            if b.bundle_id in bike_ids:
                b.rider_type, b.cost = 'BIKE', info[b.bundle_id]['cb']
            else:
                b.rider_type, b.cost = 'CAR', info[b.bundle_id]['cc']
        # 안전장치: Savings보다 나쁘면 Savings 해를 반환
        if sum(b.cost for b in result) > sum(b.cost for b in sav_bundles) + 1e-6:
            return sav_bundles, []
        return result, []

    def run(self, input_file, algorithm, output_file):
        """Provided. Do not modify."""
        start = time.perf_counter()
        if algorithm == 1:
            bundles, merges = self.solve_savings()
            name = 'SAVINGS'
        else:
            bundles, merges = self.solve_my()
            name = 'MY'
        elapsed_ms = (time.perf_counter() - start) * 1000
        write_result(output_file, input_file, len(self.orders), name, self.riders, self.dist,
                     bundles, merges, elapsed_ms)
        print(name, 'bundles =', len(bundles), 'elapsed_ms =', round(elapsed_ms, 3))


def read_instance(input_file):
    # TODO: read the rider list, the order list and the distance matrix from input_file
    # and return them so that main() can build PickupDelivery(orders, riders, dist).

    def to_number(text):
        """정수면 int, 아니면 float"""
        v = float(text)
        return int(v) if v.is_integer() else v

    # 빈 행(블록 구분)을 빼고 모든 행을 읽는다
    rows = []
    with open(input_file, newline='', encoding='utf-8-sig') as f:
        for r in csv.reader(f):
            r = [c.strip() for c in r]
            if any(c != '' for c in r):
                rows.append(r)
    n = int(float(rows[0][1]))                          # number of orders
    idx = 1
    while rows[idx][0] != 'rider_type':
        idx += 1
    idx += 1
    riders = []                                         # 라이더 블록
    while rows[idx][0] != 'order_id':
        r = rows[idx]
        riders.append(Rider(r[0], float(r[1]), to_number(r[2]), to_number(r[3]), to_number(r[4]),
                            int(float(r[5]))))
        idx += 1
    idx += 1
    orders = []                                         # 주문 블록
    for _ in range(n):
        r = rows[idx]
        orders.append(Order(int(float(r[0])), to_number(r[1]), to_number(r[2]), to_number(r[3]),
                            to_number(r[4])))
        idx += 1
    while rows[idx][0] != 'distance':
        idx += 1
    idx += 1
    dist = []                                           # 거리 행렬 (2n x 2n)
    for _ in range(2 * n):
        dist.append([to_number(c) for c in rows[idx] if c != ''])
        idx += 1
    return orders, riders, dist


def write_result(output_file, input_file, n, algorithm, riders, dist, bundles, merges, elapsed_ms):
    # TODO: write the result CSV. Match the format shown in the HW2 document (Section 2.7).
    total = sum(b.cost for b in bundles)
    bike_used = sum(1 for b in bundles if b.rider_type == 'BIKE')
    file_name = input_file.replace('\\', '/').split('/')[-1]       # 경로를 빼고 파일 이름만
    with open(output_file, 'w', newline='') as f:
        w = csv.writer(f)
        # 요약 블록
        w.writerow(['input_file', 'n', 'algorithm', 'total_cost', 'average_cost', 'bundles',
                    'bike_used', 'elapsed_ms'])
        w.writerow([file_name, n, algorithm, f'{total:.2f}', f'{total / n:.2f}', len(bundles),
                    bike_used, f'{elapsed_ms:.3f}'])
        # merge_step 블록 (Savings만, 첫 번째~세 번째 병합, 주문 ID 오름차순)
        if algorithm == 'SAVINGS':
            w.writerow(['merge_step', 'merged_orders'])
            for step, m in enumerate(merges[:3], start=1):
                w.writerow([step, ' '.join(str(o) for o in sorted(m))])
        # bundle 블록 (번들 ID 순서, 방문 순서 그대로)
        w.writerow(['bundle_id', 'rider_type', 'pickup_sequence', 'delivery_sequence', 'cost'])
        for b in sorted(bundles, key=lambda x: x.bundle_id):
            w.writerow([b.bundle_id, b.rider_type, ' '.join(str(o) for o in b.pickups),
                        ' '.join(str(o) for o in b.deliveries), f'{b.cost:.2f}'])


def main():
    # TODO: read <input_file> <algorithm_type> <output_file> from the command line.
    # If the arguments are invalid, print the usage and return 2.
    # Otherwise, read the input file, build PickupDelivery(orders, riders, dist),
    # call run(input_file, algorithm_type, output_file), and return 0.
    usage = ('Usage: python PickupDelivery_StudentID.py <input_file> <algorithm_type> <output_file>\n'
             '       algorithm_type: 1 = Savings, 2 = My Algorithm')
    # 인자 개수 / 알고리즘 번호 검사
    if len(sys.argv) != 4 or sys.argv[2] not in ('1', '2'):
        print(usage)
        return 2
    input_file, algorithm, output_file = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    try:
        orders, riders, dist = read_instance(input_file)
    except (OSError, ValueError, IndexError) as e:
        print('Cannot read input file:', e)
        print(usage)
        return 2
    PickupDelivery(orders, riders, dist).run(input_file, algorithm, output_file)
    return 0


if __name__ == '__main__':
    sys.exit(main())
