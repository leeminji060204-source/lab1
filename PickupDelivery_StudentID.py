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
        # My Algorithm
        #   (1) 번들 풀: 정확한 라벨 DP로 실행 가능한 번들(주문 집합)을 모두 열거
        #   (2) 번들 풀 위에서 주문 분할을 시뮬레이티드 어닐링(SA)으로 탐색
        #       (목적함수 = BIKE 대수 제한을 지키는 최적 라이더 배정 후의 총비용)
        #   (3) 선택된 번들의 최적 경로를 다시 만들고 검증. Savings보다 나쁘면 Savings 해 반환
        start = time.perf_counter()
        budget = TIME_LIMIT - 40            # 실제 사용 시간(초): 느린 PC/파일 입출력 대비 40초 여유
        end_time = start + budget
        max_extend = 30000                  # 번들 풀: 다음 크기로 확장할 집합 수 상한 (메모리 보호)
        n = len(self.orders)
        dist = self.dist
        riders = {}
        for r in self.riders:
            riders[r.rider_type] = r
        car, bike = riders['CAR'], riders['BIKE']
        B = bike.available
        ready = [o.ready_time for o in self.orders]
        deadline = [o.deadline for o in self.orders]
        volume = [o.volume for o in self.orders]
        ttime = {}
        for name in riders:
            ttime[name] = [[round(d / riders[name].speed) for d in row] for row in dist]

        # ---------------- 공통 함수 ----------------
        def rider_cost(rider, d):
            """고정비 + 100m당 변동비"""
            return rider.fixed_cost + rider.variable_cost * d / 100

        def route_check(pickups, deliveries, rider):
            """경로가 실행 가능하면 이동거리, 불가능하면 None"""
            if sum(volume[o] for o in pickups) > rider.capacity:
                return None
            T = ttime[rider.rider_type]
            prev = pickups[0]
            t = ready[prev]
            d = 0
            for o in pickups[1:]:
                t += T[prev][o]
                d += dist[prev][o]
                if t < ready[o]:
                    t = ready[o]
                prev = o
            for o in deliveries:
                t += T[prev][o + n]
                d += dist[prev][o + n]
                if t > deadline[o]:
                    return None
                prev = o + n
            return d

        def type_costs(pickups, deliveries):
            """(CAR 비용, BIKE 비용). 불가능한 타입은 None"""
            dc = route_check(pickups, deliveries, car)
            db = route_check(pickups, deliveries, bike)
            return (None if dc is None else rider_cost(car, dc),
                    None if db is None else rider_cost(bike, db))

        def column(cc, cb):
            """번들 정보 = (기본비용, BIKE 이득, BIKE만 가능 여부)
            기본비용: CAR 가능하면 CAR 비용, 아니면 BIKE 비용 / BIKE 이득: CAR 비용 - BIKE 비용 (양수일 때만)"""
            if cc is None:
                return (cb, 0.0, True)
            if cb is not None and cb < cc:
                return (cc, cc - cb, False)
            return (cc, 0.0, False)

        def add_label(labels, label, smaller_key_better):
            """파레토 라벨 추가: 더 좋은 라벨이 있으면 버리고, 새 라벨보다 나쁜 라벨은 지운다"""
            key, d = label[0], label[1]
            for old in labels:
                if smaller_key_better:
                    if old[0] <= key and old[1] <= d:
                        return
                elif old[0] >= key and old[1] <= d:
                    return
            keep = []
            for old in labels:
                if smaller_key_better:
                    worse = key <= old[0] and d <= old[1]
                else:
                    worse = key >= old[0] and d <= old[1]
                if not worse:
                    keep.append(old)
            keep.append(label)
            labels[:] = keep

        def remove_one(items, x):
            """정렬된 튜플에서 x를 뺀 튜플"""
            return tuple(y for y in items if y != x)

        def add_one(items, x):
            """정렬된 튜플에 x를 넣은 정렬 튜플"""
            return tuple(sorted(items + (x,)))

        # 난수 생성기 (선형 합동법, random 모듈 대신 사용)
        seed = [2026]

        def rand():
            """0 이상 1 미만의 난수"""
            seed[0] = (seed[0] * 6364136223846793005 + 1442695040888963407) % 18446744073709551616
            return (seed[0] // 2048) / 9007199254740992.0

        def pick(items):
            """리스트에서 무작위로 하나 선택"""
            return items[int(rand() * len(items))]

        # ---------------- (1) 번들 풀 ----------------
        def extend_pickups(NS, P, T):
            """마지막 픽업이 x인 픽업 라벨(시각, 거리) = (NS - x)의 라벨에서 x로 이동"""
            Pn = {}
            for x in NS:
                sub = P.get(remove_one(NS, x))
                if sub is None:
                    continue
                labels = []
                for p in sub:
                    for (t, d) in sub[p]:
                        t2 = t + T[p][x]
                        if t2 < ready[x]:
                            t2 = ready[x]
                        add_label(labels, (t2, d + dist[p][x]), True)
                if labels:
                    Pn[x] = labels
            return Pn

        def extend_deliveries(NS, Q, T):
            """첫 배달이 x인 배달 라벨(x에 늦어도 도착할 시각, 거리) = x 배달 후 (NS - x)의 배달 경로"""
            Qn = {}
            for x in NS:
                sub = Q.get(remove_one(NS, x))
                if sub is None:
                    continue
                labels = []
                for g in sub:
                    for (lt, d) in sub[g]:
                        l2 = lt - T[x + n][g + n]
                        if l2 > deadline[x]:
                            l2 = deadline[x]
                        add_label(labels, (l2, d + dist[x + n][g + n]), False)
                if labels:
                    Qn[x] = labels
            return Qn

        def join(Pn, Qn, T):
            """마지막 픽업 p -> 첫 배달 f 연결. 시간이 맞는 조합 중 최소 거리"""
            best = None
            for p in Pn:
                for f in Qn:
                    tpf = T[p][f + n]
                    dpf = dist[p][f + n]
                    for (t, d1) in Pn[p]:
                        for (lt, d2) in Qn[f]:
                            if t + tpf <= lt:
                                total = d1 + dpf + d2
                                if best is None or total < best:
                                    best = total
            return best

        def build_pool(rider, time_end):
            """실행 가능한 주문 집합을 크기 1, 2, 3, ... 순서로 열거.
            반환: {정렬된 주문 튜플: 최소 이동거리}. time_end가 지나면 그때까지의 결과 반환"""
            T = ttime[rider.rider_type]
            cap = rider.capacity
            best = {}
            P, Q = {}, {}
            level = []
            for i in range(n):                          # 크기 1 집합
                if volume[i] <= cap and ready[i] + T[i][i + n] <= deadline[i]:
                    key = (i,)
                    P[key] = {i: [(ready[i], 0)]}
                    Q[key] = {i: [(deadline[i], 0)]}
                    best[key] = dist[i][i + n]
                    level.append(key)
            comp = [set() for _ in range(n)]            # comp[i]: i와 함께 묶일 수 있는 주문들
            size = 1
            count = 0
            while level:
                size += 1
                prev = set(level)
                newP, newQ = {}, {}
                nxt = []
                for S in level:
                    last = S[-1]
                    # 후보: S의 모든 주문과 2개 묶음이 가능하고 번호가 더 큰 주문
                    if size == 2:
                        cands = range(last + 1, n)
                    else:
                        common = set(comp[S[0]])
                        for x in S[1:]:
                            common = common.intersection(comp[x])
                        cands = sorted(j for j in common if j > last)
                    vS = sum(volume[x] for x in S)
                    for j in cands:
                        if vS + volume[j] > cap:
                            continue
                        NS = S + (j,)
                        # 크기 size-1인 모든 부분집합이 실행 가능해야 후보로 인정
                        ok = True
                        for x in S:
                            if remove_one(NS, x) not in prev:
                                ok = False
                                break
                        if not ok:
                            continue
                        count += 1
                        if count % 200 == 0 and time.perf_counter() > time_end:
                            return best
                        Pn = extend_pickups(NS, P, T)
                        if not Pn:
                            continue
                        Qn = extend_deliveries(NS, Q, T)
                        if not Qn:
                            continue
                        bd = join(Pn, Qn, T)
                        if bd is None:
                            continue
                        newP[NS] = Pn
                        newQ[NS] = Qn
                        best[NS] = bd
                        nxt.append(NS)
                        if size == 2:
                            comp[S[0]].add(j)
                            comp[j].add(S[0])
                # 너무 많으면 주문당 거리가 짧은 (유망한) 집합만 다음 크기로 확장
                if len(nxt) > max_extend:
                    nxt.sort(key=lambda m: best[m] / len(m))
                    nxt = nxt[:max_extend]
                    newP = {m: newP[m] for m in nxt}
                    newQ = {m: newQ[m] for m in nxt}
                P, Q = newP, newQ                       # 이전 크기의 라벨은 버림 (메모리 절약)
                level = nxt
            return best

        # Savings 해: 초기해 + 안전장치
        sav_bundles, _ = self.solve_savings()
        sav_total = sum(b.cost for b in sav_bundles)

        # 번들 풀 만들기 (CAR는 전체 시간의 22%, BIKE는 40% 시점까지만)
        car_pool = build_pool(car, start + budget * 0.22)
        bike_pool = build_pool(bike, start + budget * 0.40)
        col = {}
        keys = set(car_pool.keys())
        keys.update(bike_pool.keys())
        for m in keys:
            dc = car_pool.get(m)
            db = bike_pool.get(m)
            info = column(None if dc is None else rider_cost(car, dc),
                          None if db is None else rider_cost(bike, db))
            col[m] = info
        for i in range(n):                              # 1개짜리 번들은 항상 포함
            if (i,) not in col:
                cc, cb = type_costs([i], [i])
                if cc is not None or cb is not None:
                    col[(i,)] = column(cc, cb)
        # 초기해 = Savings 해. 풀에 없는 Savings 번들은 그 방문 순서의 비용으로 추가
        init = []
        for b in sav_bundles:
            m = tuple(sorted(b.pickups))
            if m not in col:
                cc, cb = type_costs(b.pickups, b.deliveries)
                col[m] = column(cc, cb)
            init.append(m)
        # 이웃: 2개 묶음이 가능한 주문끼리
        nbr = [[] for _ in range(n)]
        for m in col:
            if len(m) == 2:
                nbr[m[0]].append(m[1])
                nbr[m[1]].append(m[0])

        # ---------------- (2) 시뮬레이티드 어닐링 ----------------
        # 해의 비용 = 기본비용 합 - (BIKE만 가능한 번들 수를 뺀 남은 BIKE 대수만큼의 큰 BIKE 이득 합)
        # 분할이 정해지면 이 값이 BIKE 대수 제한을 지키는 최적 라이더 배정의 비용과 같다.
        st = {}                                         # 현재 해의 상태

        def total(base, forced, advs):
            """해의 비용. BIKE만 가능한 번들이 BIKE 대수보다 많으면 None"""
            k = B - forced
            if k < 0:
                return None
            if k == 0:
                return base
            if len(advs) <= k:
                return base - sum(advs)
            return base - sum(sorted(advs, reverse=True)[:k])

        def load(sets):
            """번들 리스트로 상태 초기화"""
            st['of'] = [None] * n                       # 각 주문이 속한 번들
            st['bundles'] = set(sets)
            st['base'] = 0.0
            st['forced'] = 0
            st['advs'] = []
            for m in sets:
                c, a, f = col[m]
                st['base'] += c
                if f:
                    st['forced'] += 1
                elif a > 0:
                    st['advs'].append(a)
                for o in m:
                    st['of'][o] = m
            st['cost'] = total(st['base'], st['forced'], st['advs'])

        def try_move(removed, added):
            """removed 번들을 added 번들로 바꿨을 때의 (비용, 기본비용, forced 수, 이득 리스트)"""
            base = st['base']
            forced = st['forced']
            advs = list(st['advs'])
            for m in removed:
                c, a, f = col[m]
                base -= c
                if f:
                    forced -= 1
                elif a > 0:
                    advs.remove(a)
            for m in added:
                c, a, f = col[m]
                base += c
                if f:
                    forced += 1
                elif a > 0:
                    advs.append(a)
            cost = total(base, forced, advs)
            if cost is None:
                return None
            return (cost, base, forced, advs)

        def apply(removed, added, res):
            """이동을 실제로 반영"""
            st['cost'], st['base'], st['forced'], st['advs'] = res
            for m in removed:
                st['bundles'].discard(m)
            for m in added:
                st['bundles'].add(m)
                for o in m:
                    st['of'][o] = m

        def split_moves(A, Bm):
            """A ∪ B를 1개 또는 2개의 풀 번들로 다시 나누는 모든 방법"""
            u = tuple(sorted(A + Bm))
            moves = []
            if u in col:
                moves.append(((A, Bm), (u,)))
            parts = [[]]                                # u[1:]의 모든 부분집합
            for x in u[1:]:
                parts = parts + [p + [x] for p in parts]
            for p in parts:
                first = tuple([u[0]] + p)
                second = tuple(x for x in u if x not in first)
                if second and first in col and second in col and first != A and first != Bm:
                    moves.append(((A, Bm), (first, second)))
            return moves

        def random_moves():
            """무작위 이웃해 후보 리스트 [(지울 번들들, 추가할 번들들)]"""
            i = int(rand() * n)
            A = st['of'][i]
            r = rand()
            if r < 0.06 or not nbr[i]:                  # i를 혼자 배달하는 번들로 분리
                if len(A) == 1:
                    return []
                rest = remove_one(A, i)
                if rest not in col or (i,) not in col:
                    return []
                return [((A,), (rest, (i,)))]
            j = pick(nbr[i])
            Bm = st['of'][j]
            if Bm == A:
                return []
            if r < 0.45:                                # i를 j의 번들로 이동
                nb = add_one(Bm, i)
                na = remove_one(A, i)
                if nb not in col or (na and na not in col):
                    return []
                return [((A, Bm), (na, nb) if na else (nb,))]
            if r < 0.75:                                # i와 j 교환
                na = add_one(remove_one(A, i), j)
                nb = add_one(remove_one(Bm, j), i)
                if na not in col or nb not in col:
                    return []
                return [((A, Bm), (na, nb))]
            if r < 0.87:                                # 두 번들 합치기
                u = tuple(sorted(A + Bm))
                if u not in col:
                    return []
                return [((A, Bm), (u,))]
            if len(A) + len(Bm) > 8:                    # 두 번들 재분할 (크기 제한)
                return []
            return split_moves(A, Bm)

        load(init)
        best_cost = st['cost']
        best_sets = list(st['bundles'])
        avg = st['cost'] / max(1, len(best_sets))
        t_start, t_end = 0.1 * avg, 0.001 * avg         # 시작/끝 온도 (실험으로 정한 값)
        sa_start = time.perf_counter()
        cycle_len = max(end_time - sa_start, 0.001) / 2  # 2구간: 매 구간 최고해에서 다시 가열
        cycle_start = sa_start
        temp = t_start
        it = 0
        while True:
            it += 1
            if it % 300 == 0:
                now = time.perf_counter()
                if now >= end_time:
                    break
                prog = (now - cycle_start) / cycle_len
                if prog >= 1.0:                         # 다음 구간: 최고해에서 재시작
                    cycle_start = now
                    prog = 0.0
                    load(best_sets)
                temp = t_start * (t_end / t_start) ** prog
            chosen = None                               # 후보 중 가장 좋은 이동 선택
            for removed, added in random_moves():
                res = try_move(removed, added)
                if res is not None and (chosen is None or res[0] < chosen[2][0]):
                    chosen = (removed, added, res)
            if chosen is None:
                continue
            removed, added, res = chosen
            delta = res[0] - st['cost']
            # 좋아지면 항상, 나빠지면 확률 e^(-delta/temp)로 받아들임
            if delta <= 1e-9 or rand() < 2.718281828459045 ** (-delta / temp):
                apply(removed, added, res)
                if st['cost'] < best_cost - 1e-9:
                    best_cost = st['cost']
                    best_sets = list(st['bundles'])

        # ---------------- (3) 최적 경로 복원 + 라이더 배정 + 검증 ----------------
        def best_route(members, rider):
            """주문 집합 하나의 최소 거리 경로 (부분집합 DP, 정확해). 반환: (거리, 픽업순서, 배달순서)"""
            T = ttime[rider.rider_type]
            if sum(volume[o] for o in members) > rider.capacity:
                return None
            k = len(members)
            # 픽업 DP: (픽업한 집합, 마지막 픽업) -> [(시각, 거리, 경로)]
            P = {}
            layer = []
            for o in members:
                key = (frozenset([o]), o)
                P[key] = [(ready[o], 0, (o,))]
                layer.append(key)
            for _ in range(k - 1):
                new = {}
                for key in layer:
                    s, last = key
                    for j in members:
                        if j in s:
                            continue
                        labels = new.setdefault((s.union([j]), j), [])
                        for (t, d, path) in P[key]:
                            t2 = max(t + T[last][j], ready[j])
                            add_label(labels, (t2, d + dist[last][j], path + (j,)), True)
                P.update(new)
                layer = list(new.keys())
            # 배달 DP (뒤에서부터): (배달 집합, 첫 배달) -> [(첫 배달 최대 도착시각, 거리, 경로)]
            Q = {}
            layer = []
            for o in members:
                key = (frozenset([o]), o)
                Q[key] = [(deadline[o], 0, (o,))]
                layer.append(key)
            for _ in range(k - 1):
                new = {}
                for key in layer:
                    s, first = key
                    for g in members:
                        if g in s:
                            continue
                        labels = new.setdefault((s.union([g]), g), [])
                        for (lt, d, path) in Q[key]:
                            l2 = min(lt - T[g + n][first + n], deadline[g])
                            add_label(labels, (l2, d + dist[g + n][first + n], (g,) + path), False)
                Q.update(new)
                layer = list(new.keys())
            full = frozenset(members)
            best = None
            for p in members:
                for (t, d1, pp) in P.get((full, p), []):
                    for f in members:
                        arrive = t + T[p][f + n]
                        for (lt, d2, dp) in Q.get((full, f), []):
                            if arrive <= lt:
                                d = d1 + dist[p][f + n] + d2
                                if best is None or d < best[0]:
                                    best = (d, list(pp), list(dp))
            return best

        def build_bundles(sets):
            """선택된 주문 집합으로 Bundle을 만들고 최적 라이더 배정
            (BIKE만 가능한 번들 먼저, 나머지 BIKE는 이득이 큰 순서로)"""
            bundles = []
            routes = {}
            forced = []
            cand = []
            for m in sets:
                members = list(m)
                rc = best_route(members, car)
                rb = best_route(members, bike)
                if rc is None and rb is None:
                    return None
                b = Bundle(members[0], None, None)
                cc = None if rc is None else rider_cost(car, rc[0])
                cb = None if rb is None else rider_cost(bike, rb[0])
                routes[b.bundle_id] = {'CAR': (rc, cc), 'BIKE': (rb, cb)}
                if cc is None:
                    forced.append(b.bundle_id)
                elif cb is not None and cb < cc:
                    cand.append((-(cc - cb), b.bundle_id))
                bundles.append(b)
            if len(forced) > B:
                return None
            cand.sort()
            bike_ids = forced + [bid for _, bid in cand[:B - len(forced)]]
            for b in bundles:
                rtype = 'BIKE' if b.bundle_id in bike_ids else 'CAR'
                route, cost = routes[b.bundle_id][rtype]
                b.rider_type = rtype
                b.cost = cost
                b.pickups = route[1]
                b.deliveries = route[2]
            bundles.sort(key=lambda x: x.bundle_id)
            return bundles

        def is_valid(bundles):
            """모든 제약 검증: 주문 정확히 1번, BIKE 대수, 용량/시간 제약, 비용 일치"""
            count = [0] * n
            bike_used = 0
            for b in bundles:
                if sorted(b.pickups) != sorted(b.deliveries):
                    return False
                for o in b.pickups:
                    count[o] += 1
                rider = riders[b.rider_type]
                if b.rider_type == 'BIKE':
                    bike_used += 1
                d = route_check(b.pickups, b.deliveries, rider)
                if d is None or abs(rider_cost(rider, d) - b.cost) > 1e-6:
                    return False
            return bike_used <= B and all(c == 1 for c in count)

        my_bundles = build_bundles(best_sets)
        if my_bundles is not None and is_valid(my_bundles):
            if sum(b.cost for b in my_bundles) <= sav_total + 1e-6:
                return my_bundles, []
        return sav_bundles, []

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
