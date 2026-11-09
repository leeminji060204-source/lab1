import csv
import sys
import time
import math
import random

TIME_LIMIT = 300    # seconds. Algorithm 2 must finish within this limit (measured by the TA).
MY_TIME_BUDGET = TIME_LIMIT - 40    # My Algorithm이 실제로 쓰는 시간(초). 느린 PC/파일 입출력 대비 40초 여유
MAX_EXTEND = 30000                  # 번들 풀: 한 크기에서 다음 크기로 확장할 집합 수 상한 (메모리 보호)


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


def add_label(labels, label, smaller_key_better):
    """파레토 라벨 리스트에 label(key, 거리, ...)을 추가한다.
    key가 더 좋고 거리도 더 짧은 라벨이 이미 있으면 추가하지 않고,
    새 라벨보다 나쁜 기존 라벨은 지운다."""
    key, dist = label[0], label[1]
    for old in labels:
        if smaller_key_better:
            dominated = old[0] <= key and old[1] <= dist
        else:
            dominated = old[0] >= key and old[1] <= dist
        if dominated:
            return
    keep = []
    for old in labels:
        if smaller_key_better:
            worse = key <= old[0] and dist <= old[1]
        else:
            worse = key >= old[0] and dist <= old[1]
        if not worse:
            keep.append(old)
    keep.append(label)
    labels[:] = keep


def remove_one(items, x):
    """정렬된 튜플 items에서 x 하나를 뺀 튜플"""
    return tuple(y for y in items if y != x)


def add_one(items, x):
    """정렬된 튜플 items에 x를 넣은 정렬 튜플"""
    return tuple(sorted(items + (x,)))


class PickupDelivery:
    def __init__(self, orders, riders, dist):
        self.orders = orders
        self.riders = riders
        self.dist = dist
        self.n = len(orders)
        # 타입 이름으로 라이더 찾기
        self.bike = None
        self.car = None
        for r in riders:
            if r.rider_type == 'BIKE':
                self.bike = r
            elif r.rider_type == 'CAR':
                self.car = r
        # 라이더 타입별 이동시간 행렬: round(distance / speed) (파이썬 내장 round)
        self.ttime = {}
        for r in riders:
            self.ttime[r.rider_type] = [[round(d / r.speed) for d in row] for row in dist]
        self.ready = [o.ready_time for o in orders]
        self.deadline = [o.deadline for o in orders]
        self.volume = [o.volume for o in orders]

    # ------------------------------------------------------------------ #
    # 공통 함수
    # ------------------------------------------------------------------ #
    def route_check(self, pickups, deliveries, rider):
        """경로를 시뮬레이션해서 실행 가능하면 이동거리, 불가능하면 None을 반환"""
        if sum(self.volume[o] for o in pickups) > rider.capacity:    # 용량 제약
            return None
        n = self.n
        T = self.ttime[rider.rider_type]
        D = self.dist
        prev = pickups[0]
        t = self.ready[prev]            # 첫 픽업 장소를 ready time에 출발
        d = 0
        for o in pickups[1:]:
            t += T[prev][o]
            d += D[prev][o]
            if t < self.ready[o]:       # 일찍 도착하면 ready time까지 대기
                t = self.ready[o]
            prev = o
        for o in deliveries:            # 픽업을 모두 끝낸 뒤 배달
            t += T[prev][o + n]
            d += D[prev][o + n]
            if t > self.deadline[o]:    # 마감시간 위반
                return None
            prev = o + n
        return d

    def rider_cost(self, rider, distance):
        """고정비 + 100m당 변동비"""
        return rider.fixed_cost + rider.variable_cost * distance / 100

    def type_costs(self, pickups, deliveries):
        """주어진 방문 순서의 (CAR 비용, BIKE 비용). 불가능한 타입은 None"""
        dc = self.route_check(pickups, deliveries, self.car)
        db = self.route_check(pickups, deliveries, self.bike)
        cc = None if dc is None else self.rider_cost(self.car, dc)
        cb = None if db is None else self.rider_cost(self.bike, db)
        return cc, cb

    def cheaper(self, cc, cb):
        """가능한 타입 중 더 싼 비용 (BIKE 대수 제한은 무시)"""
        if cb is None:
            return cc
        if cc is None:
            return cb
        return min(cc, cb)

    # ------------------------------------------------------------------ #
    # 1) Savings 알고리즘
    # ------------------------------------------------------------------ #
    def best_merge(self, A, B):
        """번들 A, B (A의 ID < B의 ID)를 합치는 4가지 후보 중 가장 싼 것.
        CAR로 불가능한 후보는 제외. 반환: (비용, 픽업순서, 배달순서) 또는 None"""
        if A['vol'] + B['vol'] > self.car.capacity:
            return None
        pa, pb, da, db = A['p'], B['p'], A['d'], B['d']
        # 리스트 순서 = 과제에서 정한 동점 처리 순서
        candidates = [(pa + pb, da + db), (pa + pb, db + da), (pb + pa, da + db), (pb + pa, db + da)]
        best = None
        for ps, ds in candidates:
            cc, cb = self.type_costs(ps, ds)
            if cc is None:                      # CAR로 불가능하면 허용 안 함
                continue
            c = self.cheaper(cc, cb)
            if best is None or c < best[0]:     # 동점이면 앞의 후보 유지
                best = (c, ps, ds)
        return best

    def update_saving(self, savings, bund, a, b):
        """번들 쌍 (a, b)의 saving을 계산해서 양수일 때만 딕셔너리에 저장"""
        res = self.best_merge(bund[a], bund[b])
        if res is None:
            return
        saving = round(bund[a]['cost'] + bund[b]['cost'] - res[0], 2)
        if saving > 0:
            savings[(a, b)] = (saving, res)

    def solve_savings(self):
        n = self.n
        # A. 초기: 주문 하나당 번들 하나 (번들 ID = 가장 작은 주문 ID)
        bund = {}
        for i in range(n):
            cc, cb = self.type_costs([i], [i])
            bund[i] = {'p': [i], 'd': [i], 'vol': self.volume[i], 'cost': self.cheaper(cc, cb)}

        # B. 모든 쌍 (A의 ID < B의 ID)의 saving 계산
        savings = {}
        for a in range(n):
            for b in range(a + 1, n):
                self.update_saving(savings, bund, a, b)

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
                    self.update_saving(savings, bund, min(a, x), max(a, x))

        # E. 라이더 배정
        bundles = []
        for bid in sorted(bund):
            bundles.append(Bundle(bid, bund[bid]['p'], bund[bid]['d']))
        self.assign_savings_riders(bundles)
        return bundles, merges

    def assign_savings_riders(self, bundles):
        """BIKE가 더 싼 번들에 (CAR 비용 - BIKE 비용)이 큰 순서로 BIKE 배정 (동점이면 작은 ID 먼저)"""
        cand = []
        costs = {}
        for b in bundles:
            cc, cb = self.type_costs(b.pickups, b.deliveries)
            costs[b.bundle_id] = (cc, cb)
            if cb is not None and cb < cc:
                cand.append((-round(cc - cb, 2), b.bundle_id))
        cand.sort()
        bike_ids = [bid for _, bid in cand[:self.bike.available]]
        for b in bundles:
            cc, cb = costs[b.bundle_id]
            if b.bundle_id in bike_ids:
                b.rider_type, b.cost = 'BIKE', cb
            else:
                b.rider_type, b.cost = 'CAR', cc

    # ------------------------------------------------------------------ #
    # 2) My Algorithm
    #   (1) BundlePool: 정확한 라벨 DP로 실행 가능한 번들(주문 집합)을 모두 열거
    #   (2) PartitionSearch: 번들 풀 위에서 집합 분할을 시뮬레이티드 어닐링으로 탐색
    #       (목적함수 = BIKE 대수 제한을 지키는 최적 라이더 배정 후의 총비용)
    #   (3) 선택된 번들의 최적 경로를 다시 만들고 실행 가능성을 검증
    #       (Savings 해와 비교해서 더 좋은 해를 반환하므로 결과가 항상 안전)
    # ------------------------------------------------------------------ #
    def solve_my(self):
        start = time.perf_counter()
        end_time = start + MY_TIME_BUDGET

        # Savings 해: 초기해 + 안전장치
        sav_bundles, _ = self.solve_savings()
        sav_total = sum(b.cost for b in sav_bundles)

        # (1) 번들 풀 만들기 (CAR 22%, BIKE 18% 시간까지만 사용)
        car_pool = BundlePool(self, self.car).build(start + MY_TIME_BUDGET * 0.22)
        bike_pool = BundlePool(self, self.bike).build(start + MY_TIME_BUDGET * 0.40)
        columns = self.make_columns(car_pool, bike_pool)

        # 초기해 = Savings 해. 풀에 없는 Savings 번들은 그 방문 순서의 비용으로 추가
        init = []
        for b in sav_bundles:
            m = tuple(sorted(b.pickups))
            if m not in columns:
                cc, cb = self.type_costs(b.pickups, b.deliveries)
                adv = cc - cb if (cb is not None and cb < cc) else 0.0
                columns[m] = (cc, adv, False)
            init.append(m)

        # (2) 시뮬레이티드 어닐링
        search = PartitionSearch(self.n, columns, self.bike.available, random.Random(2026))
        best_sets = search.run(init, end_time)

        # (3) 최적 경로 복원 + 라이더 배정 + 검증
        my_bundles = self.build_bundles(best_sets)
        if my_bundles is not None and self.is_valid(my_bundles):
            my_total = sum(b.cost for b in my_bundles)
            if my_total <= sav_total + 1e-6:
                return my_bundles, []
        return sav_bundles, []

    def make_columns(self, car_pool, bike_pool):
        """번들 집합 -> (기본비용, BIKE 이득, BIKE만 가능 여부)
        기본비용: CAR 가능하면 CAR 비용, 아니면 BIKE 비용
        BIKE 이득: CAR 비용 - BIKE 비용 (BIKE가 더 쌀 때만, 아니면 0)"""
        columns = {}
        keys = set(car_pool.keys())
        keys.update(bike_pool.keys())
        for i in range(self.n):                 # 1개짜리 번들은 항상 포함
            keys.add((i,))
        for m in keys:
            dc = car_pool.get(m)
            db = bike_pool.get(m)
            if dc is None and db is None:       # 풀에 없는 1개짜리는 직접 계산
                cc, cb = self.type_costs([m[0]], [m[0]])
            else:
                cc = None if dc is None else self.rider_cost(self.car, dc)
                cb = None if db is None else self.rider_cost(self.bike, db)
            if cc is not None:
                adv = cc - cb if (cb is not None and cb < cc) else 0.0
                columns[m] = (cc, adv, False)
            elif cb is not None:
                columns[m] = (cb, 0.0, True)
        return columns

    def best_route(self, members, rider):
        """주문 집합 하나의 최소 거리 경로 (부분집합 DP, 정확해).
        반환: (거리, 픽업순서, 배달순서) 또는 None"""
        n = self.n
        T = self.ttime[rider.rider_type]
        D = self.dist
        if sum(self.volume[o] for o in members) > rider.capacity:
            return None
        k = len(members)
        # 픽업 DP: (픽업한 집합, 마지막 픽업) -> [(시각, 거리, 경로)]
        P = {}
        layer = []
        for o in members:
            key = (frozenset([o]), o)
            P[key] = [(self.ready[o], 0, (o,))]
            layer.append(key)
        for _ in range(k - 1):
            new = {}
            for key in layer:
                s, last = key
                for j in members:
                    if j in s:
                        continue
                    nkey = (s.union([j]), j)
                    labels = new.setdefault(nkey, [])
                    for (t, d, path) in P[key]:
                        t2 = max(t + T[last][j], self.ready[j])
                        add_label(labels, (t2, d + D[last][j], path + (j,)), True)
            P.update(new)
            layer = list(new.keys())
        # 배달 DP (뒤에서부터): (배달 집합, 첫 배달) -> [(첫 배달 지점 최대 도착시각, 거리, 경로)]
        Q = {}
        layer = []
        for o in members:
            key = (frozenset([o]), o)
            Q[key] = [(self.deadline[o], 0, (o,))]
            layer.append(key)
        for _ in range(k - 1):
            new = {}
            for key in layer:
                s, first = key
                for g in members:
                    if g in s:
                        continue
                    nkey = (s.union([g]), g)
                    labels = new.setdefault(nkey, [])
                    for (lt, d, path) in Q[key]:
                        l2 = min(lt - T[g + n][first + n], self.deadline[g])
                        add_label(labels, (l2, d + D[g + n][first + n], (g,) + path), False)
            Q.update(new)
            layer = list(new.keys())
        # 마지막 픽업 p -> 첫 배달 f 로 연결
        full = frozenset(members)
        best = None
        for p in members:
            for (t, d1, pp) in P.get((full, p), []):
                for f in members:
                    arrive = t + T[p][f + n]
                    for (lt, d2, dp) in Q.get((full, f), []):
                        if arrive <= lt:
                            total = d1 + D[p][f + n] + d2
                            if best is None or total < best[0]:
                                best = (total, list(pp), list(dp))
        return best

    def build_bundles(self, sets):
        """선택된 주문 집합들로 Bundle을 만들고 최적 라이더 배정"""
        bundles = []
        forced = []         # BIKE만 가능한 번들
        cand = []           # BIKE가 더 싼 번들 후보
        for m in sets:
            members = list(m)
            rc = self.best_route(members, self.car)
            rb = self.best_route(members, self.bike)
            if rc is None and rb is None:
                return None
            b = Bundle(members[0], None, None)
            b.routes = {'CAR': rc, 'BIKE': rb}
            b.cc = None if rc is None else self.rider_cost(self.car, rc[0])
            b.cb = None if rb is None else self.rider_cost(self.bike, rb[0])
            if b.cc is None:
                forced.append(b)
            elif b.cb is not None and b.cb < b.cc:
                cand.append((-(b.cc - b.cb), b.bundle_id, b))
            bundles.append(b)
        if len(forced) > self.bike.available:
            return None
        cand.sort(key=lambda x: (x[0], x[1]))
        bike_ids = [b.bundle_id for b in forced]
        for item in cand[:self.bike.available - len(forced)]:
            bike_ids.append(item[1])
        for b in bundles:
            rtype = 'BIKE' if b.bundle_id in bike_ids else 'CAR'
            b.rider_type = rtype
            b.cost = b.cb if rtype == 'BIKE' else b.cc
            b.pickups = b.routes[rtype][1]
            b.deliveries = b.routes[rtype][2]
        bundles.sort(key=lambda x: x.bundle_id)
        return bundles

    def is_valid(self, bundles):
        """모든 제약 검증: 주문 정확히 1번, BIKE 대수, 용량/시간 제약, 비용 일치"""
        count = [0] * self.n
        bike_used = 0
        for b in bundles:
            if sorted(b.pickups) != sorted(b.deliveries):
                return False
            for o in b.pickups:
                count[o] += 1
            rider = self.bike if b.rider_type == 'BIKE' else self.car
            if b.rider_type == 'BIKE':
                bike_used += 1
            d = self.route_check(b.pickups, b.deliveries, rider)
            if d is None or abs(self.rider_cost(rider, d) - b.cost) > 1e-6:
                return False
        return bike_used <= self.bike.available and all(c == 1 for c in count)

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


class BundlePool:
    """한 라이더 타입에 대해 실행 가능한 주문 집합을 크기 1, 2, 3, ... 순서로 열거한다.
    P[집합][마지막 픽업] = [(마지막 픽업 시각, 거리)]                 (픽업 경로의 파레토 라벨)
    Q[집합][첫 배달]     = [(첫 배달 지점에 늦어도 도착해야 할 시각, 거리)] (배달 경로의 파레토 라벨)
    크기 k 집합의 라벨은 크기 k-1 집합의 라벨을 확장해서 만든다."""

    def __init__(self, problem, rider):
        self.pb = problem
        self.rider = rider

    def build(self, time_end):
        """반환: {정렬된 주문 튜플: 최소 이동거리}. time_end가 지나면 그때까지의 결과 반환"""
        pb = self.pb
        n = pb.n
        T = pb.ttime[self.rider.rider_type]
        D = pb.dist
        ready, dl, vol, cap = pb.ready, pb.deadline, pb.volume, self.rider.capacity
        best = {}
        P, Q = {}, {}
        level = []
        for i in range(n):                      # 크기 1 집합
            if vol[i] <= cap and ready[i] + T[i][i + n] <= dl[i]:
                key = (i,)
                P[key] = {i: [(ready[i], 0)]}
                Q[key] = {i: [(dl[i], 0)]}
                best[key] = D[i][i + n]
                level.append(key)
        comp = [set() for _ in range(n)]        # comp[i]: i와 함께 묶일 수 있는 주문들
        size = 1
        count = 0
        while level:
            size += 1
            prev = set(level)
            newP, newQ = {}, {}
            nxt = []
            for S in level:
                last = S[-1]
                # 추가할 후보: S의 모든 주문과 2개 묶음이 가능한 주문 중 번호가 더 큰 것
                if size == 2:
                    cands = range(last + 1, n)
                else:
                    common = set(comp[S[0]])
                    for x in S[1:]:
                        common = common.intersection(comp[x])
                    cands = sorted(j for j in common if j > last)
                vS = sum(vol[x] for x in S)
                for j in cands:
                    if vS + vol[j] > cap:
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
                    Pn = self.extend_pickups(NS, P, T, D, ready)
                    if not Pn:
                        continue
                    Qn = self.extend_deliveries(NS, Q, T, D, dl, n)
                    if not Qn:
                        continue
                    bd = self.join(Pn, Qn, T, D, n)
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
            if len(nxt) > MAX_EXTEND:
                nxt.sort(key=lambda m: best[m] / len(m))
                nxt = nxt[:MAX_EXTEND]
                newP = {m: newP[m] for m in nxt}
                newQ = {m: newQ[m] for m in nxt}
            P, Q = newP, newQ                   # 이전 크기의 라벨은 더 이상 필요 없음 (메모리 절약)
            level = nxt
        return best

    def extend_pickups(self, NS, P, T, D, ready):
        """마지막 픽업이 x인 픽업 라벨 = (NS - x)의 라벨에서 x로 이동"""
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
                    add_label(labels, (t2, d + D[p][x]), True)
            if labels:
                Pn[x] = labels
        return Pn

    def extend_deliveries(self, NS, Q, T, D, dl, n):
        """첫 배달이 x인 배달 라벨 = x를 배달한 뒤 (NS - x)의 배달 경로로 이어감"""
        Qn = {}
        for x in NS:
            sub = Q.get(remove_one(NS, x))
            if sub is None:
                continue
            labels = []
            for g in sub:
                for (lt, d) in sub[g]:
                    l2 = lt - T[x + n][g + n]
                    if l2 > dl[x]:
                        l2 = dl[x]
                    add_label(labels, (l2, d + D[x + n][g + n]), False)
            if labels:
                Qn[x] = labels
        return Qn

    def join(self, Pn, Qn, T, D, n):
        """마지막 픽업 p -> 첫 배달 f 연결. 시간이 맞는 조합 중 최소 거리"""
        best = None
        for p in Pn:
            for f in Qn:
                tpf = T[p][f + n]
                dpf = D[p][f + n]
                for (t, d1) in Pn[p]:
                    for (lt, d2) in Qn[f]:
                        if t + tpf <= lt:
                            total = d1 + dpf + d2
                            if best is None or total < best:
                                best = total
        return best


class PartitionSearch:
    """번들 풀(columns) 위에서 주문 분할을 시뮬레이티드 어닐링으로 개선한다.
    해의 비용 = 기본비용 합 - (BIKE만 가능한 번들 수를 뺀 남은 BIKE 대수만큼의 큰 BIKE 이득 합)
    -> 분할이 정해지면 이것이 BIKE 대수 제한을 지키는 최적 라이더 배정의 비용과 같다."""

    def __init__(self, n, columns, bike_limit, rng):
        self.n = n
        self.col = columns
        self.B = bike_limit
        self.rng = rng
        # 이웃: 2개 묶음이 가능한 주문끼리
        self.nbr = [[] for _ in range(n)]
        for m in columns:
            if len(m) == 2:
                self.nbr[m[0]].append(m[1])
                self.nbr[m[1]].append(m[0])

    def total(self, base, forced, advs):
        """현재 값들로 해의 비용 계산. BIKE만 가능한 번들이 너무 많으면 None"""
        k = self.B - forced
        if k < 0:
            return None
        if k == 0:
            return base
        if len(advs) <= k:
            return base - sum(advs)
        return base - sum(sorted(advs, reverse=True)[:k])

    def load(self, sets):
        """번들 리스트로 상태 초기화"""
        self.of = [None] * self.n       # 각 주문이 속한 번들
        self.bundles = set(sets)
        self.base = 0.0
        self.forced = 0
        self.advs = []
        for m in sets:
            c, a, f = self.col[m]
            self.base += c
            if f:
                self.forced += 1
            elif a > 0:
                self.advs.append(a)
            for o in m:
                self.of[o] = m
        self.cost = self.total(self.base, self.forced, self.advs)

    def try_move(self, removed, added):
        """removed 번들을 added 번들로 바꿨을 때의 (비용, 기본비용, forced 수, 이득 리스트)"""
        base = self.base
        forced = self.forced
        advs = list(self.advs)
        for m in removed:
            c, a, f = self.col[m]
            base -= c
            if f:
                forced -= 1
            elif a > 0:
                advs.remove(a)
        for m in added:
            c, a, f = self.col[m]
            base += c
            if f:
                forced += 1
            elif a > 0:
                advs.append(a)
        cost = self.total(base, forced, advs)
        if cost is None:
            return None
        return (cost, base, forced, advs)

    def apply(self, removed, added, res):
        """이동을 실제로 반영"""
        self.cost, self.base, self.forced, self.advs = res
        for m in removed:
            self.bundles.discard(m)
        for m in added:
            self.bundles.add(m)
            for o in m:
                self.of[o] = m

    def split_moves(self, A, Bm):
        """A ∪ B를 1개 또는 2개의 풀 번들로 다시 나누는 모든 방법"""
        u = tuple(sorted(A + Bm))
        moves = []
        if u in self.col:
            moves.append(((A, Bm), (u,)))
        rest = u[1:]
        parts = [[]]                    # rest의 모든 부분집합 (u[0]은 항상 첫 번째 쪽)
        for x in rest:
            parts = parts + [p + [x] for p in parts]
        for p in parts:
            first = tuple([u[0]] + p)
            second = tuple(x for x in u if x not in first)
            if second and first in self.col and second in self.col and first != A and first != Bm:
                moves.append(((A, Bm), (first, second)))
        return moves

    def random_moves(self):
        """무작위 이웃해 후보 리스트 [(지울 번들들, 추가할 번들들)]"""
        rng = self.rng
        i = rng.randrange(self.n)
        A = self.of[i]
        r = rng.random()
        if r < 0.06 or not self.nbr[i]:             # i를 혼자 배달하는 번들로 분리
            if len(A) == 1:
                return []
            rest = remove_one(A, i)
            if rest not in self.col:
                return []
            return [((A,), (rest, (i,)))]
        j = rng.choice(self.nbr[i])
        Bm = self.of[j]
        if Bm == A:
            return []
        if r < 0.45:                                # i를 j의 번들로 이동
            nb = add_one(Bm, i)
            na = remove_one(A, i)
            if nb not in self.col or (na and na not in self.col):
                return []
            return [((A, Bm), (na, nb) if na else (nb,))]
        if r < 0.75:                                # i와 j 교환
            na = add_one(remove_one(A, i), j)
            nb = add_one(remove_one(Bm, j), i)
            if na not in self.col or nb not in self.col:
                return []
            return [((A, Bm), (na, nb))]
        if r < 0.87:                                # 두 번들 합치기
            u = tuple(sorted(A + Bm))
            if u not in self.col:
                return []
            return [((A, Bm), (u,))]
        if len(A) + len(Bm) > 8:                    # 두 번들 재분할 (크기 제한)
            return []
        return self.split_moves(A, Bm)

    def run(self, init, end_time):
        """시뮬레이티드 어닐링. 시간을 2구간으로 나눠 매 구간 최고해에서 다시 가열"""
        self.load(init)
        best_cost = self.cost
        best = list(self.bundles)
        avg = self.cost / max(1, len(self.bundles))
        t_start, t_end = 0.1 * avg, 0.001 * avg       # 시작/끝 온도 (실험으로 정한 값)
        start = time.perf_counter()
        cycle_len = max(end_time - start, 1e-3) / 2
        cycle_start = start
        temp = t_start
        it = 0
        while True:
            it += 1
            if it % 300 == 0:
                now = time.perf_counter()
                if now >= end_time:
                    break
                prog = (now - cycle_start) / cycle_len
                if prog >= 1.0:                       # 다음 구간: 최고해에서 재시작
                    cycle_start = now
                    prog = 0.0
                    self.load(best)
                temp = t_start * (t_end / t_start) ** prog
            # 후보 중 가장 좋은 이동 선택
            chosen = None
            for removed, added in self.random_moves():
                res = self.try_move(removed, added)
                if res is not None and (chosen is None or res[0] < chosen[2][0]):
                    chosen = (removed, added, res)
            if chosen is None:
                continue
            removed, added, res = chosen
            delta = res[0] - self.cost
            if delta <= 1e-9 or self.rng.random() < math.exp(-delta / temp):
                self.apply(removed, added, res)
                if self.cost < best_cost - 1e-9:
                    best_cost = self.cost
                    best = list(self.bundles)
        return best


def to_number(text):
    """정수면 int, 아니면 float"""
    v = float(text)
    return int(v) if v.is_integer() else v


def read_instance(input_file):
    """입력 파일에서 라이더, 주문, 거리 행렬을 읽는다 (블록 사이 빈 행은 건너뜀)"""
    with open(input_file, newline='') as f:
        rows = []
        for r in csv.reader(f):
            r = [c.strip() for c in r]
            if any(c != '' for c in r):
                rows.append(r)
    n = int(float(rows[0][1]))
    idx = 1
    while rows[idx][0] != 'rider_type':
        idx += 1
    idx += 1
    riders = []
    while rows[idx][0] != 'order_id':
        r = rows[idx]
        riders.append(Rider(r[0], float(r[1]), to_number(r[2]), to_number(r[3]), to_number(r[4]),
                            int(float(r[5]))))
        idx += 1
    idx += 1
    orders = []
    for _ in range(n):
        r = rows[idx]
        orders.append(Order(int(float(r[0])), to_number(r[1]), to_number(r[2]), to_number(r[3]),
                            to_number(r[4])))
        idx += 1
    while rows[idx][0] != 'distance':
        idx += 1
    idx += 1
    dist = []
    for _ in range(2 * n):
        dist.append([to_number(c) for c in rows[idx] if c != ''])
        idx += 1
    return orders, riders, dist


def write_result(output_file, input_file, n, algorithm, riders, dist, bundles, merges, elapsed_ms):
    """결과 CSV 저장 (과제 2.7절 형식)"""
    total = sum(b.cost for b in bundles)
    bike_used = sum(1 for b in bundles if b.rider_type == 'BIKE')
    with open(output_file, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['input_file', 'n', 'algorithm', 'total_cost', 'average_cost', 'bundles',
                    'bike_used', 'elapsed_ms'])
        w.writerow([input_file, n, algorithm, f'{total:.2f}', f'{total / n:.2f}', len(bundles),
                    bike_used, f'{elapsed_ms:.3f}'])
        if algorithm == 'SAVINGS':      # My Algorithm은 merge_step 블록을 쓰지 않음
            w.writerow(['merge_step', 'merged_orders'])
            for step, m in enumerate(merges[:3], start=1):      # 첫 번째~세 번째 병합
                w.writerow([step, ' '.join(str(o) for o in sorted(m))])
        w.writerow(['bundle_id', 'rider_type', 'pickup_sequence', 'delivery_sequence', 'cost'])
        for b in sorted(bundles, key=lambda x: x.bundle_id):
            w.writerow([b.bundle_id, b.rider_type, ' '.join(str(o) for o in b.pickups),
                        ' '.join(str(o) for o in b.deliveries), f'{b.cost:.2f}'])


def main():
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
