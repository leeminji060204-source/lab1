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
        # Savings에서 출발하여 합치기, 주문 이동, 교환을 반복한다.
        # 개선이 멈추면 일부 번들을 풀고 다시 탐색한다. 난수는 사용하지 않는다.
        # 이번 탐색의 최고 기록이 30초 동안 개선되지 않으면,
        # 최초 지역 탐색 결과로 돌아가 흔들기 시작 위치를 바꾼다.
        end_time = time.perf_counter() + max(0, TIME_LIMIT - 40)
        n = len(self.orders)
        dist = self.dist
        riders = {r.rider_type: r for r in self.riders}
        car, bike = riders['CAR'], riders['BIKE']

        orders = sorted(self.orders, key=lambda o: o.order_id)
        ready = [o.ready_time for o in orders]
        deadline = [o.deadline for o in orders]
        volume = [o.volume for o in orders]

        # 같은 이동시간을 반복해서 계산하지 않도록 미리 저장한다.
        travel = {}
        for name in riders:
            travel[name] = [
                [round(d / riders[name].speed) for d in row]
                for row in dist
            ]

        def route_cost(p, d, rider):
            # 첫 픽업의 준비 완료 시각에 출발한다.
            # 이후 픽업 장소에 일찍 도착하면 준비 완료까지 기다린다.
            if not p or sum(volume[i] for i in p) > rider.capacity:
                return None

            prev = p[0]
            now = ready[prev]
            length = 0
            T = travel[rider.rider_type]

            for i in p[1:]:
                now = max(now + T[prev][i], ready[i])
                length += dist[prev][i]
                prev = i

            for i in d:
                # 배달 위치는 거리 행렬에서 주문 번호 + n이다.
                now += T[prev][i + n]
                length += dist[prev][i + n]

                if now > deadline[i]:
                    return None

                prev = i + n

            return rider.fixed_cost + rider.variable_cost * length / 100

        def make(p, d):
            # 두 라이더의 실행 가능 여부와 비용을 함께 저장한다.
            cc = route_cost(p, d, car)
            cb = route_cost(p, d, bike)

            if cc is None and cb is None:
                return None

            return {'p': p, 'd': d, 'cc': cc, 'cb': cb}

        def total(sol):
            # 반드시 BIKE가 필요한 번들에 먼저 배정한다.
            # 나머지는 CAR 대비 절약액이 큰 순서로 BIKE를 배정한다.
            cost, forced = 0, 0
            gains = []

            for b in sol:
                if b['cc'] is None:
                    cost += b['cb']
                    forced += 1
                else:
                    cost += b['cc']

                    if b['cb'] is not None and b['cb'] < b['cc']:
                        gains.append(b['cc'] - b['cb'])

            left = bike.available - forced

            if left < 0:
                return float('inf')

            gains.sort(reverse=True)
            return cost - sum(gains[:left])

        cache = {}

        def insert(b, i):
            # 모든 픽업/배달 삽입 위치를 검사한다.
            # CAR 최저비용 경로와 BIKE 최저비용 경로를 각각 남긴다.
            if b is None:
                single = make([i], [i])
                return [] if single is None else [single]

            key = (tuple(b['p']), tuple(b['d']), i)

            if key in cache:
                return cache[key]

            best_car, best_bike = None, None

            for x in range(len(b['p']) + 1):
                for y in range(len(b['d']) + 1):
                    if time.perf_counter() >= end_time:
                        # 중단한 계산은 완성된 결과처럼 저장하지 않는다.
                        return []

                    p = b['p'][:x] + [i] + b['p'][x:]
                    d = b['d'][:y] + [i] + b['d'][y:]
                    c = make(p, d)

                    if c is None:
                        continue

                    if c['cc'] is not None:
                        if best_car is None or c['cc'] < best_car['cc']:
                            best_car = c

                    if c['cb'] is not None:
                        if best_bike is None or c['cb'] < best_bike['cb']:
                            best_bike = c

            result = []

            if best_car is not None:
                result.append(best_car)

            if best_bike is not None and best_bike != best_car:
                result.append(best_bike)

            # 저장 공간이 계속 커지는 것을 막는다.
            if len(cache) >= 20000:
                cache.clear()

            cache[key] = result
            return result

        def remove(b, i):
            p = [o for o in b['p'] if o != i]

            if not p:
                return None  # 주문이 없어져 빈 번들이 된 경우

            d = [o for o in b['d'] if o != i]
            c = make(p, d)

            # 빈 번들(None)과 실행 불가능한 경로(False)를 구분한다.
            return False if c is None else c

        def cheaper(b):
            # 가능한 라이더 중 더 싼 비용 (끼워 넣기 합치기에서 경로를 고를 때 사용)
            if b['cc'] is None:
                return b['cb']

            if b['cb'] is not None and b['cb'] < b['cc']:
                return b['cb']

            return b['cc']

        def insert_all(A, B):
            # B의 주문을 픽업 순서대로 A에 하나씩 끼워 넣는다.
            # 매번 insert가 돌려준 후보 중 더 싼 경로를 고르고, 넣을 수 없으면 None
            cur = A

            for i in B['p']:
                options = insert(cur, i)

                if not options:
                    return None

                cur = options[0]

                for c in options[1:]:
                    if cheaper(c) < cheaper(cur):
                        cur = c

            return cur

        def replace(sol, indices, added):
            # 기존 해를 직접 수정하지 않고 새 리스트를 만든다.
            new = [
                sol[k] for k in range(len(sol))
                if k not in indices
            ]

            for b in added:
                if b is not None:
                    new.append(b)

            return new

        def positions(sol):
            # 주문 번호 -> 해당 주문이 속한 번들의 리스트 위치
            pos = [0] * n

            for k in range(len(sol)):
                for i in sol[k]['p']:
                    pos[i] = k

            return pos

        # 가까운 주문만 이동/교환 대상으로 삼아 탐색 시간을 줄인다.
        # 거리뿐 아니라 준비 시각의 차이도 함께 고려한다.
        near = []

        for i in range(n):
            pairs = []

            for j in range(n):
                if i != j:
                    gap = (
                        dist[i][j]
                        + dist[i + n][j + n]
                        + abs(ready[i] - ready[j]) * car.speed
                    )
                    pairs.append((gap, j))

            pairs.sort()
            near.append([j for _, j in pairs[:10]])

        def improve(sol):
            # 비용이 감소하는 변경 하나를 찾으면 반환한다.
            # 이후 변경된 해를 기준으로 처음부터 다시 검사한다.
            current = total(sol)
            pos = positions(sol)

            # 1. 두 번들의 픽업/배달 순서를 앞뒤로 연결해서 합친다.
            for a in range(len(sol)):
                for b in range(a + 1, len(sol)):
                    if time.perf_counter() >= end_time:
                        return None

                    A, B = sol[a], sol[b]
                    pickups = [
                        A['p'] + B['p'],
                        B['p'] + A['p']
                    ]
                    deliveries = [
                        A['d'] + B['d'],
                        B['d'] + A['d']
                    ]

                    candidates = []

                    for p in pickups:
                        for d in deliveries:
                            merged = make(p, d)

                            if merged is not None:
                                candidates.append(merged)

                    # 한 번들의 주문을 다른 번들에 하나씩 가장 싼 위치로 끼워 넣어서 합치는 방법도
                    # B -> A, A -> B 두 방향 모두 시도한다.
                    for merged in [insert_all(A, B), insert_all(B, A)]:
                        if merged is not None:
                            candidates.append(merged)

                    for merged in candidates:
                        new = replace(sol, [a, b], [merged])

                        if total(new) < current - 1e-6:
                            return new

            for i in range(n):
                if time.perf_counter() >= end_time:
                    return None

                a = pos[i]
                rest = remove(sol[a], i)

                if rest is False:
                    continue

                # 2. 자기 번들 안에서 위치를 바꾸거나,
                # 가까운 주문이 속한 다른 번들로 이동한다.
                targets = [a]

                for j in near[i]:
                    if pos[j] not in targets:
                        targets.append(pos[j])

                for b in targets:
                    target = rest if a == b else sol[b]

                    for candidate in insert(target, i):
                        if a == b:
                            new = replace(sol, [a], [candidate])
                        else:
                            new = replace(
                                sol, [a, b], [rest, candidate]
                            )

                        # BIKE 대수를 반영한 전체 비용으로 비교한다.
                        if total(new) < current - 1e-6:
                            return new

                # 3. 주문 i를 혼자 배달하는 번들로 분리한다.
                if rest is not None:
                    single = make([i], [i])

                    if single is not None:
                        new = replace(sol, [a], [rest, single])

                        if total(new) < current - 1e-6:
                            return new

                # 4. 서로 다른 번들의 주문 i와 j를 교환한다.
                for j in near[i]:
                    if time.perf_counter() >= end_time:
                        return None

                    b = pos[j]

                    if a == b:
                        continue

                    other = remove(sol[b], j)

                    if other is False:
                        continue

                    for na in insert(rest, j):
                        for nb in insert(other, i):
                            new = replace(sol, [a, b], [na, nb])

                            if total(new) < current - 1e-6:
                                return new

            return None

        def local_search(sol):
            # 개선되는 변경이 없거나 시간이 끝날 때까지 반복한다.
            while time.perf_counter() < end_time:
                new = improve(sol)

                if new is None:
                    break

                sol = new

            return sol

        def perturb(sol, step):
            # 시작 주문을 0, 1, ..., n-1 순서로 바꾼다.
            # 한 바퀴 돌 때마다 분리할 번들 수를 2, 3, 4개로 바꾼다.
            pos = positions(sol)
            i = step % n
            size = 2 + (step // n) % 3
            chosen = [pos[i]]

            for j in near[i]:
                if len(chosen) >= size:
                    break

                if pos[j] not in chosen:
                    chosen.append(pos[j])

            singles = []

            for k in chosen:
                for o in sol[k]['p']:
                    single = make([o], [o])

                    if single is None:
                        # 분리할 수 없는 주문을 누락시키지 않는다.
                        return sol

                    singles.append(single)

            new = replace(sol, chosen, singles)

            if total(new) == float('inf'):
                return sol

            return new

        # 초기해는 기존 solve_savings의 반환값만 이용한다.
        sav_bundles, _ = self.solve_savings()

        if n == 0:
            return sav_bundles, []

        sol = []

        for b in sav_bundles:
            c = make(list(b.pickups), list(b.deliveries))

            if c is None:
                return sav_bundles, []

            sol.append(c)

        start_sol = local_search(sol)       # 모든 탐색의 공통 출발점
        best, best_cost = start_sol, total(start_sol)       # 전체 최고 기록
        run_best, run_cost = best, best_cost                # 이번 탐색의 최고 기록
        sol = start_sol
        step = 0
        offset = 0          # 이번 탐색에서 흔들기를 시작하는 주문 번호
        last_improve = time.perf_counter()

        while time.perf_counter() < end_time:
            new = local_search(perturb(sol, offset + step))
            step += 1
            cost = total(new)

            if cost < run_cost - 1e-6:
                run_best, run_cost = new, cost
                last_improve = time.perf_counter()

            if cost < best_cost - 1e-6:
                best, best_cost = new, cost

            # 약간 나쁜 해도 다음 탐색의 출발점으로 허용한다.
            # 이번 탐색의 최고 기록보다 1% 넘게 나쁘면 그 기록으로 돌아간다.
            sol = new if cost <= run_cost * 1.01 else run_best

            # 이번 탐색의 최고 기록이 30초 동안 개선되지 않으면 탐색이 멈춘 것으로 보고,
            # 최초 지역 탐색 결과로 돌아가 흔들기 시작 위치를 n/3만큼 옮겨 새로 탐색한다.
            if time.perf_counter() - last_improve > 30:
                offset += n // 3 + 1
                step = 0
                sol = start_sol
                run_best, run_cost = start_sol, total(start_sol)
                last_improve = time.perf_counter()

        # 반환 직전에 주문 누락/중복, 경로, 비용, BIKE 대수를 검증한다.
        counts = [0] * n

        for b in best:
            if not b['p'] or sorted(b['p']) != sorted(b['d']):
                return sav_bundles, []

            for i in b['p']:
                if i < 0 or i >= n:
                    return sav_bundles, []

                counts[i] += 1

            if make(b['p'], b['d']) != b:
                return sav_bundles, []

        if any(c != 1 for c in counts) or total(best) == float('inf'):
            return sav_bundles, []

        # 실제 라이더 배정: 필수 BIKE부터 배정하고 절약액 순으로 추가 배정.
        forced, gains = [], []

        for b in best:
            bid = min(b['p'])

            if b['cc'] is None:
                forced.append(bid)
            elif b['cb'] is not None and b['cb'] < b['cc']:
                gains.append((-(b['cc'] - b['cb']), bid))

        # 절약액 내림차순, 동률이면 번들 번호 오름차순.
        gains.sort()
        bike_ids = forced + [
            bid for _, bid in gains[:bike.available - len(forced)]
        ]

        result = []

        for b in best:
            bid = min(b['p'])
            item = Bundle(bid, b['p'][:], b['d'][:])
            item.rider_type = 'BIKE' if bid in bike_ids else 'CAR'
            item.cost = b['cb'] if bid in bike_ids else b['cc']
            result.append(item)

        # Savings보다 나빠졌다면 원래 Savings 결과를 반환한다.
        if sum(b.cost for b in result) > sum(b.cost for b in sav_bundles) + 1e-6:
            return sav_bundles, []

        result.sort(key=lambda b: b.bundle_id)
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
