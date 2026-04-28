import random
import numpy as np
from collections import defaultdict

# ... (نفس Class SATInstance كما في السابق) ...

class TrinitarianSATSolverV2:
    def __init__(self, sat_instance):
        self.sat = sat_instance
        self.cells = {}  # key: frozenset of assignment items, value: dict with 'bs','parent','stagnation'
        self.root = frozenset()
        self.cells[self.root] = {'bs': 0.0, 'parent': None, 'stagnation': 0}
        self.best_solution = None
        self.best_sat = 0

    def bs(self, assignment):
        """BS محسّن يركز على العبارات غير المُرضاة"""
        if not assignment:
            return 0.0
        sat_count = self.sat.evaluate(assignment)
        # BS يمثل جودة التعيين مقارنة بالحل المثالي
        return sat_count / self.sat.total_clauses()

    def choose_variable(self, assignment):
        """اختيار المتغير الأكثر تأثيرًا في العبارات غير المُرضاة حاليًا"""
        unsatisfied = [c for c in self.sat.clauses if 
                       not any(abs(lit) in assignment and (assignment[abs(lit)] == (lit>0)) for lit in c)]
        var_scores = defaultdict(int)
        for var in range(1, self.sat.num_vars+1):
            if var in assignment: continue
            # كم عبارة غير راضية تحتوي على هذا المتغير؟
            for clause in unsatisfied:
                if any(abs(lit)==var for lit in clause):
                    var_scores[var] += 1
        if not var_scores:
            # كل المتغيرات معينة، لا يمكن الانقسام
            return None
        # اختر الأعلى تأثيرًا (أو عشوائيًا من بين الأعلى)
        best_score = max(var_scores.values())
        best_vars = [v for v, s in var_scores.items() if s == best_score]
        return random.choice(best_vars)

    def split_cell(self, cell_key):
        """الانقسام المحسّن: نستخدم اختيار المتغير الذكي ونولد خليتين بالتوازي"""
        assignment = dict(cell_key)
        var = self.choose_variable(assignment)
        if var is None:
            return []  # لا مزيد من المتغيرات
        new_cells = []
        for val in [True, False]:
            new_assignment = dict(assignment)
            new_assignment[var] = val
            new_key = frozenset(new_assignment.items())
            new_cells.append(new_key)
        return new_cells

    def entangle_cells(self, cell1_key, cell2_key):
        """
        تشابك خليتين: إذا اختلفتا في قيمة متغير واحد فقط، نولد خلية جديدة بقيمة بديلة.
        هذه محاولة للجمع بين المسارات الواعدة.
        """
        ass1 = dict(cell1_key)
        ass2 = dict(cell2_key)
        common_vars = set(ass1.keys()) & set(ass2.keys())
        if len(ass1) != len(ass2) or len(common_vars) != len(ass1)-1:
            return None  # لا يمكن تطبيق التشابك حالياً
        # ابحث عن المتغير المختلف
        diff_vars = [v for v in ass1 if v in ass2 and ass1[v]!=ass2[v]]
        if len(diff_vars)!=1:
            return None
        var = diff_vars[0]
        # أنشئ خلية جديدة بقيمة مختلفة
        new_assignment = dict(ass1)
        new_assignment[var] = not ass1[var]
        return frozenset(new_assignment.items())

    def back_to_potential(self):
        """العودة إلى الإمكان: نحذف نصف الخلايا الأقل BS ونستبدلها بجذر جديد (إعادة ضبط محلي)"""
        if len(self.cells) < 5:
            return
        sorted_cells = sorted(self.cells.items(), key=lambda x: x[1]['bs'])
        remove_count = max(1, len(sorted_cells)//3)
        for i in range(remove_count):
            key = sorted_cells[i][0]
            del self.cells[key]
        # إضافة خلية إمكان جديدة مبنية على أفضل خلية حالية ولكن مع حذف متغيرين
        if self.best_solution:
            best_assignment = dict(self.best_solution)
            if len(best_assignment) > 2:
                vars_to_remove = random.sample(list(best_assignment.keys()), 2)
                for v in vars_to_remove:
                    del best_assignment[v]
            new_key = frozenset(best_assignment.items())
            self.cells[new_key] = {'bs': self.bs(best_assignment), 'parent': None, 'stagnation': 0}

    def evolve(self, max_steps=100, bs_threshold=0.5, patience=10):
        """التطور مع آليات جديدة"""
        stagnation_counter = 0
        best_ever = 0
        for step in range(max_steps):
            # 1. دمج المتناقضات
            self.merge_contradictions()
            if not self.cells:
                break

            # 2. تحديث BS للكل وتحديد الأفضل
            bs_values = {}
            for key in self.cells:
                bs_val = self.bs(dict(key))
                self.cells[key]['bs'] = bs_val
                bs_values[key] = bs_val
            best_key = max(bs_values, key=bs_values.get)
            best_bs = bs_values[best_key]

            # تحديث أفضل حل كامل
            for key in self.cells:
                ass = dict(key)
                if len(ass) == self.sat.num_vars:
                    sat_count = self.sat.evaluate(ass)
                    if sat_count > best_ever:
                        best_ever = sat_count
                        self.best_solution = frozenset(ass.items())
                        if sat_count > self.best_sat:
                            self.best_sat = sat_count
                            stagnation_counter = 0

            # 3. فحص الركود
            if step > 0 and best_bs <= (self.best_sat / self.sat.total_clauses()):
                stagnation_counter += 1
            else:
                stagnation_counter = 0

            # 4. إذا حدث ركود، نطبق العودة إلى الإمكان
            if stagnation_counter >= patience:
                print(f"Step {step}: ركود، العودة إلى الإمكان...")
                self.back_to_potential()
                stagnation_counter = 0
                continue

            # 5. الانقسام مع إمكانية التشابك
            if best_bs >= bs_threshold:
                new_keys = self.split_cell(best_key)
                if new_keys:
                    del self.cells[best_key]
                    for nk in new_keys:
                        self.cells[nk] = {'bs': 0.0, 'parent': best_key, 'stagnation': 0}
                else:
                    # الخلية مكتملة لكنها ليست حلًا كاملًا (يجب أن تُحذف في merge)
                    pass
            else:
                # اختر عشوائيًا مع تفضيل الأعلى (استكشاف)
                top_keys = sorted(bs_values, key=bs_values.get, reverse=True)[:max(1, len(bs_values)//5)]
                chosen = random.choice(top_keys)
                new_keys = self.split_cell(chosen)
                if new_keys:
                    del self.cells[chosen]
                    for nk in new_keys:
                        self.cells[nk] = {'bs': 0.0, 'parent': chosen, 'stagnation': 0}

            # 6. تطبيق التشابك بين الخلايا العليا (اختياري)
            if step % 10 == 0 and len(self.cells) >= 2:
                top_two = sorted(bs_values, key=bs_values.get, reverse=True)[:2]
                if len(top_two)==2:
                    maybe_cell = self.entangle_cells(top_two[0], top_two[1])
                    if maybe_cell and maybe_cell not in self.cells:
                        self.cells[maybe_cell] = {'bs': self.bs(dict(maybe_cell)), 'parent': 'entangled', 'stagnation':0}

            # 7. عرض تقدم كل 10 خطوات
            if step % 10 == 0 or step == max_steps-1:
                best_sat = max(bs_values.values()) * self.sat.total_clauses() if bs_values else 0
                print(f"Step {step}: Cells={len(self.cells)}, Best sat={int(best_sat)}/{self.sat.total_clauses()}, Best ever={best_ever}")
                if best_ever == self.sat.total_clauses():
                    print("وجدنا حلاً!")
                    break

    def find_solution(self):
        if self.best_solution:
            return dict(self.best_solution)
        for key in self.cells:
            ass = dict(key)
            if len(ass) == self.sat.num_vars and self.sat.evaluate(ass) == self.sat.total_clauses():
                return ass
        return None
