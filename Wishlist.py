import sys
import os
import json
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
                             QPushButton, QGroupBox, QScrollArea, QLabel, QMessageBox, QDoubleSpinBox,
                             QSizePolicy, QListWidget, QListWidgetItem, QAbstractItemView, QProgressBar,
                             QGraphicsColorizeEffect)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize
from PyQt5.QtGui import QColor, QFont, QPalette, QDoubleValidator


class WishItem:
    """Класс для элементов списка желаний"""

    def __init__(self, name="Новая вещь", cost=0, progress=0, position=0):
        self.name = name
        self.cost = int(round(cost))  # Всегда целое число
        self.progress = int(round(progress))  # Всегда целое число
        self.preview_progress = int(round(progress))  # Для предварительного просмотра изменений
        self.position = position  # Позиция для сохранения порядка
        self.item = None  # Ссылка на связанный QListWidgetItem

    @property
    def remaining(self):
        """Оставшаяся сумма для завершения"""
        return max(0, self.cost - self.progress)

    @property
    def preview_remaining(self):
        """Оставшаяся сумма в режиме предпросмотра"""
        return max(0, self.cost - self.preview_progress)

    def to_dict(self):
        """Сериализация в словарь"""
        return {
            'name': self.name,
            'cost': self.cost,
            'progress': self.progress,
            'position': self.position
        }

    @classmethod
    def from_dict(cls, data):
        """Создание объекта из словаря"""
        cost = data['cost']
        progress = data['progress']
        position = data.get('position', 0)

        # Конвертация в целые числа
        if isinstance(cost, float):
            cost = int(round(cost))
        if isinstance(progress, float):
            progress = int(round(progress))
        return cls(data['name'], cost, progress, position)


class Category:
    """Класс для категорий желаний"""

    def __init__(self, name="Новая категория", percent=0):
        self.name = name
        self.percent = percent
        self.wishes = []
        self.widget = None  # Ссылка на виджет категории
        self.allocated = 0  # Выделенная сумма при расчете

    @property
    def sorted_wishes(self):
        """Желания отсортированные по позиции"""
        return sorted(self.wishes, key=lambda w: w.position)

    @property
    def total_cost(self):
        """Общая стоимость всех желаний"""
        return sum(w.cost for w in self.wishes)

    @property
    def total_progress(self):
        """Текущий прогресс по всем желаниям"""
        return sum(w.progress for w in self.wishes)

    @property
    def total_preview_progress(self):
        """Прогресс в режиме предпросмотра"""
        return sum(w.preview_progress for w in self.wishes)

    @property
    def uncompleted_wishes(self):
        """Незавершенные желания"""
        return [w for w in self.wishes if w.progress < w.cost]

    @property
    def uncompleted_preview_wishes(self):
        """Незавершенные желания в предпросмотре"""
        return [w for w in self.wishes if w.preview_progress < w.cost]

    @property
    def total_remaining(self):
        """Общая оставшаяся сумма по категории"""
        return sum(w.remaining for w in self.wishes)

    @property
    def total_preview_remaining(self):
        """Оставшаяся сумма в предпросмотре"""
        return sum(w.preview_remaining for w in self.wishes)

    def add_wish(self, wish):
        """Добавление нового желания"""
        wish.position = len(self.wishes)
        self.wishes.append(wish)

    def to_dict(self):
        """Сериализация в словарь"""
        return {
            'name': self.name,
            'percent': self.percent,
            'wishes': [w.to_dict() for w in self.wishes]
        }

    @classmethod
    def from_dict(cls, data):
        """Создание объекта из словаря"""
        cat = cls(data['name'], data['percent'])
        wishes = [WishItem.from_dict(w) for w in data['wishes']]
        cat.wishes = sorted(wishes, key=lambda w: w.position)
        return cat


class WishlistApp(QMainWindow):
    """Главное окно приложения"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wishlist")
        self.setMinimumSize(800, 600)
        self.categories = []
        self.current_budget = 0

        # Настройка путей для сохранения данных
        documents_path = os.path.expanduser('~/Documents')
        self.wishlist_dir = os.path.join(documents_path, 'Wishlist')
        os.makedirs(self.wishlist_dir, exist_ok=True)
        self.data_file = os.path.join(self.wishlist_dir, "wishlist_data.json")

        self.load_data()  # Загрузка сохраненных данных
        self.init_ui()  # Инициализация интерфейса
        self.apply_styles()  # Применение стилей

    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)

        # Панель управления
        control_layout = QHBoxLayout()

        # Поле ввода бюджета
        self.budget_input = QLineEdit()
        self.budget_input.setPlaceholderText("Сумма для внесения")
        self.budget_input.setValidator(QDoubleValidator(0, 1000000, 2))
        self.budget_input.setFixedHeight(40)

        # Кнопки управления
        self.calc_button = QPushButton("Рассчитать")
        self.calc_button.setFixedHeight(40)
        self.calc_button.clicked.connect(self.calculate_distribution)

        self.apply_button = QPushButton("Внести")
        self.apply_button.setFixedHeight(40)
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.apply_distribution)

        self.help_button = QPushButton("?")
        self.help_button.setFixedSize(40, 40)
        self.help_button.setStyleSheet("""
            QPushButton {
                font-weight: bold;
                font-size: 18px;
                border-radius: 20px;
                background-color: #9C27B0;
                color: white;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
        """)
        self.help_button.clicked.connect(self.show_help)

        # Добавление элементов на панель управления
        control_layout.addWidget(self.budget_input, 3)
        control_layout.addWidget(self.calc_button, 1)
        control_layout.addWidget(self.apply_button, 1)
        control_layout.addWidget(self.help_button)

        # Информационные метки
        self.distribution_label = QLabel()
        self.distribution_label.setAlignment(Qt.AlignCenter)
        self.distribution_label.setStyleSheet("color: #777777; font-size: 12px;")
        self.distribution_label.setVisible(False)

        self.remaining_label = QLabel()
        self.remaining_label.setAlignment(Qt.AlignCenter)
        self.remaining_label.setStyleSheet("color: #ff5722; font-size: 12px; font-weight: bold;")
        self.remaining_label.setVisible(False)

        # Кнопка сброса
        self.reset_button = QPushButton("Сбросить расчёт")
        self.reset_button.setFixedHeight(40)
        self.reset_button.setStyleSheet("""
            QPushButton {
                background-color: #9E9E9E;
                color: white;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #757575;
            }
        """)
        self.reset_button.clicked.connect(self.reset_calculation)
        self.reset_button.setVisible(False)

        # Область с категориями
        self.categories_scroll = QScrollArea()
        self.categories_scroll.setWidgetResizable(True)
        self.categories_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        self.categories_container = QWidget()
        self.categories_layout = QHBoxLayout(self.categories_container)
        self.categories_layout.setAlignment(Qt.AlignLeft)

        # Кнопка добавления категории
        self.add_category_btn = QPushButton("+")
        self.add_category_btn.setFixedSize(60, 60)
        self.add_category_btn.setStyleSheet("""
            QPushButton {
                font-size: 24px;
                font-weight: bold;
                border-radius: 30px;
                background-color: #4CAF50;
                color: white;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.add_category_btn.clicked.connect(self.add_category)
        self.categories_layout.addWidget(self.add_category_btn)
        self.categories_scroll.setWidget(self.categories_container)

        # Добавление существующих категорий
        for category in self.categories:
            self.add_category_ui(category)

        # Компоновка главного окна
        main_layout.addLayout(control_layout)
        main_layout.addWidget(self.distribution_label)
        main_layout.addWidget(self.remaining_label)
        main_layout.addWidget(self.reset_button, 0, Qt.AlignCenter)
        main_layout.addWidget(self.categories_scroll, 1)

        self.setCentralWidget(main_widget)

    # Основные методы приложения
    def show_help(self):
        """Отображение окна справки"""
        help_text = """
        <h2>Как пользоваться Wishlist</h2>
        <p>Приложение для управления списком желаний с распределением бюджета</p>
        <h3>Основные функции:</h3>
        <ul>
            <li><b>Добавление категорий</b>: Кнопка "+" справа</li>
            <li><b>Добавление желаний</b>: "+ Добавить желание" внутри категории</li>
            <li><b>Установка процентов</b>: Для каждой категории</li>
            <li><b>Распределение бюджета</b>:
                <ol>
                    <li>Введите сумму</li>
                    <li>Нажмите "Рассчитать"</li>
                    <li>Нажмите "Внести" для применения</li>
                </ol>
            </li>
        </ul>
        """
        msg = QMessageBox()
        msg.setWindowTitle("Справка")
        msg.setTextFormat(Qt.RichText)
        msg.setText(help_text)
        msg.setIcon(QMessageBox.Information)
        msg.exec_()

    def reset_calculation(self):
        """Сброс предварительного расчета"""
        for category in self.categories:
            for wish in category.wishes:
                wish.preview_progress = wish.progress
        self.update_ui()
        self.distribution_label.setVisible(False)
        self.remaining_label.setVisible(False)
        self.reset_button.setVisible(False)
        self.apply_button.setEnabled(False)

    def add_category_ui(self, category):
        """Добавление UI для категории"""
        group_box = QGroupBox()
        group_box.setMinimumWidth(280)
        group_layout = QVBoxLayout(group_box)
        group_layout.setSpacing(5)

        # Заголовок категории
        name_layout = QHBoxLayout()
        name_label = QLineEdit(category.name)
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        name_label.textChanged.connect(lambda text, cat=category: self.update_category_name(cat, text))
        name_layout.addWidget(name_label)

        # Процент категории
        percent_spin = QDoubleSpinBox()
        percent_spin.setRange(0, 100)
        percent_spin.setValue(category.percent)
        percent_spin.setSuffix("%")
        percent_spin.setAlignment(Qt.AlignRight)
        percent_spin.valueChanged.connect(lambda val, cat=category: self.update_category_percent(cat, val))
        name_layout.addWidget(percent_spin)

        # Кнопка удаления
        delete_btn = QPushButton("×")
        delete_btn.setFixedSize(24, 24)
        delete_btn.setStyleSheet("""
            QPushButton {
                font-weight: bold;
                border-radius: 12px;
                background-color: #f44336;
                color: white;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        delete_btn.clicked.connect(lambda _, cat=category, gb=group_box: self.remove_category(cat, gb))
        name_layout.addWidget(delete_btn)
        group_layout.addLayout(name_layout)

        # Прогресс категории
        progress_text = f"{category.total_progress:,.0f}/{category.total_cost:,.0f}"
        progress_label = QLabel(progress_text)
        progress_label.setAlignment(Qt.AlignCenter)
        progress_label.setStyleSheet("font-size: 14px;")
        group_layout.addWidget(progress_label)

        # Прогресс-бар
        cat_progress = QProgressBar()
        cat_progress.setFixedHeight(8)
        cat_progress.setRange(0, category.total_cost)
        cat_progress.setValue(category.total_progress)
        cat_progress.setFormat("")
        cat_progress.setStyleSheet(self.get_category_progress_style(category.total_progress, category.total_cost))
        group_layout.addWidget(cat_progress)

        # Список желаний
        wish_list = QListWidget()
        wish_list.setDragDropMode(QAbstractItemView.InternalMove)
        wish_list.setStyleSheet("QListWidget { border: none; }")
        wish_list.model().rowsMoved.connect(
            lambda: self.update_wish_positions(category, wish_list)
        )
        for wish in category.sorted_wishes:
            self.add_wish_item(wish_list, wish)
        group_layout.addWidget(wish_list)

        # Кнопка добавления желания
        add_wish_btn = QPushButton("+ Добавить желание")
        add_wish_btn.clicked.connect(lambda _, cat=category, wl=wish_list: self.add_wish(cat, wl))
        group_layout.addWidget(add_wish_btn)

        # Сохранение ссылок
        category.widget = group_box
        category.progress_label = progress_label
        category.progress_bar = cat_progress
        category.wish_list = wish_list

        # Добавление в интерфейс
        self.categories_layout.insertWidget(self.categories_layout.count() - 1, group_box)

    def update_wish_positions(self, category, wish_list):
        """Обновление позиций после перемещения элементов"""
        for i in range(wish_list.count()):
            item = wish_list.item(i)
            if hasattr(item, 'wish'):
                item.wish.position = i
        self.save_data()

    def add_wish_item(self, list_widget, wish):
        """Добавление элемента желания в список"""
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 60))
        item.wish = wish
        wish.item = item

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # Верхняя панель с названием и стоимостью
        name_layout = QHBoxLayout()
        name_edit = QLineEdit(wish.name)
        name_edit.setCursorPosition(0)
        name_edit.textChanged.connect(lambda text, w=wish: self.update_wish_name(w, text))
        name_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        name_layout.addWidget(name_edit, 6)

        cost_edit = QLineEdit(str(wish.cost))
        cost_edit.setValidator(QDoubleValidator(0, 1000000, 2))
        cost_edit.textChanged.connect(lambda text, w=wish: self.update_wish_cost(w, text))
        cost_edit.setFixedWidth(45)
        name_layout.addWidget(cost_edit, 2)
        name_layout.addWidget(QLabel("₽"))

        # Кнопка редактирования
        edit_btn = QPushButton()
        edit_btn.setFixedSize(25, 25)
        edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        edit_btn.setText("🖉")
        name_layout.addWidget(edit_btn, 1)
        layout.addLayout(name_layout)

        # Прогресс-бар
        progress = QProgressBar()
        progress.setRange(0, wish.cost)
        progress.setValue(wish.progress)
        progress.setStyleSheet(self.get_wish_progress_style(wish.progress, wish.cost))
        progress.setFormat(
            f"{wish.progress:,.0f}/{wish.cost:,.0f} ({wish.progress / wish.cost * 100:.1f}%)" if wish.cost > 0 else "0/0 (0%)")
        layout.addWidget(progress)

        # Панель управления
        edit_panel = QWidget()
        edit_layout = QHBoxLayout(edit_panel)
        edit_layout.setContentsMargins(0, 0, 0, 0)
        edit_layout.setSpacing(5)
        edit_panel.setVisible(False)

        amount_input = QLineEdit()
        amount_input.setPlaceholderText("Сумма")
        amount_input.setValidator(QDoubleValidator(0, 1000000, 2))
        amount_input.setFixedHeight(25)
        edit_layout.addWidget(amount_input)

        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(5)

        # Кнопки управления
        plus_btn = QPushButton("+")
        plus_btn.setFixedSize(25, 25)
        plus_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                font-size: 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        plus_btn.clicked.connect(lambda: self.adjust_wish_progress(wish, amount_input.text(), True))

        minus_btn = QPushButton("-")
        minus_btn.setFixedSize(25, 25)
        minus_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        minus_btn.clicked.connect(lambda: self.adjust_wish_progress(wish, amount_input.text(), False))

        delete_btn = QPushButton("🗑")
        delete_btn.setFixedSize(25, 25)
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #9E9E9E;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #757575;
            }
        """)
        delete_btn.clicked.connect(lambda: self.delete_wish(wish, list_widget, item))
        btn_layout.addWidget(plus_btn)
        btn_layout.addWidget(minus_btn)
        btn_layout.addWidget(delete_btn)

        edit_layout.addWidget(btn_container)
        layout.addWidget(edit_panel)

        # Сохранение ссылок
        item.edit_panel = edit_panel
        item.amount_input = amount_input
        edit_btn.clicked.connect(lambda: self.toggle_edit_panel(item))
        wish.progress_bar = progress

        list_widget.addItem(item)
        list_widget.setItemWidget(item, widget)

    def toggle_edit_panel(self, item):
        """Переключение панели редактирования"""
        item.edit_panel.setVisible(not item.edit_panel.isVisible())
        height = 100 if item.edit_panel.isVisible() else 60
        item.setSizeHint(QSize(0, height))
        item.listWidget().doItemsLayout()

    def adjust_wish_progress(self, wish, amount_text, is_positive):
        """Изменение прогресса желания"""
        try:
            amount = float(amount_text) if amount_text else 0
            amount = int(round(amount))
        except:
            return

        if is_positive:
            new_progress = min(wish.progress + amount, wish.cost)
        else:
            new_progress = max(0, wish.progress - amount)

        wish.progress = new_progress
        wish.preview_progress = new_progress
        self.update_ui()
        self.save_data()
        wish.item.amount_input.clear()

    def delete_wish(self, wish, list_widget, item):
        """Удаление желания"""
        for category in self.categories:
            if wish in category.wishes:
                category.wishes.remove(wish)
                break
        list_widget.takeItem(list_widget.row(item))
        self.update_ui()
        self.save_data()

    # Методы для работы с прогрессом
    def get_category_progress_style(self, progress, total):
        """Стиль прогресс-бара категории"""
        if total == 0:
            return ""

        percentage = progress / total * 100
        base_style = """
            QProgressBar {
                height: 8px;
                border: none;
                border-radius: 4px;
                background-color: rgba(200, 200, 200, 100);
            }
            QProgressBar::chunk {
                border-radius: 4px;
            }
        """

        if percentage >= 100:
            return base_style + """
                QProgressBar::chunk {
                    background-color: rgba(255, 215, 0, 150);
                }
            """
        elif percentage > 0:
            return base_style + """
                QProgressBar::chunk {
                    background-color: rgba(76, 175, 80, 150);
                }
            """
        else:
            return base_style + """
                QProgressBar::chunk {
                    background-color: rgba(200, 200, 200, 50);
                }
            """

    def get_wish_progress_style(self, progress, total):
        """Стиль прогресс-бара желания"""
        if total == 0:
            return ""

        percentage = progress / total * 100
        if percentage >= 100:
            return """
                QProgressBar {
                    height: 18px;
                    border: 1px solid #FFD700;
                    border-radius: 5px;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background-color: #FFD700;
                }
            """
        elif percentage > 0:
            return """
                QProgressBar {
                    height: 18px;
                    border: 1px solid #4CAF50;
                    border-radius: 5px;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background-color: #4CAF50;
                }
            """
        else:
            return """
                QProgressBar {
                    height: 18px;
                    border: 1px solid #CCCCCC;
                    border-radius: 5px;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background-color: #CCCCCC;
                }
            """

    # Методы обновления данных
    def update_category_name(self, category, name):
        category.name = name
        self.save_data()

    def update_category_percent(self, category, percent):
        category.percent = percent
        self.save_data()

    def update_wish_name(self, wish, name):
        wish.name = name
        self.save_data()

    def update_wish_cost(self, wish, text):
        try:
            cost = float(text) if text else 0
            wish.cost = int(round(cost))
            wish.progress = min(wish.progress, wish.cost)
            wish.preview_progress = wish.progress
            self.update_ui()
            self.save_data()
        except:
            pass

    def add_category(self):
        """Добавление новой категории"""
        new_category = Category(f"Категория {len(self.categories) + 1}", 10)
        self.categories.append(new_category)
        self.add_category_ui(new_category)
        self.save_data()

    def remove_category(self, category, group_box):
        """Удаление категории"""
        self.categories.remove(category)
        group_box.deleteLater()
        self.save_data()

    def add_wish(self, category, list_widget):
        """Добавление нового желания"""
        new_wish = WishItem("Новая вещь", 1000)
        category.add_wish(new_wish)
        self.add_wish_item(list_widget, new_wish)
        self.save_data()

    def calculate_distribution(self):
        """Расчет распределения бюджета"""
        try:
            budget = float(self.budget_input.text())
            budget = int(round(budget))
            if budget <= 0:
                QMessageBox.warning(self, "Ошибка", "Введите положительную сумму")
                return
        except:
            QMessageBox.warning(self, "Ошибка", "Некорректная сумма")
            return

        # Сброс предыдущих расчетов
        for category in self.categories:
            category.allocated = 0
            for wish in category.wishes:
                wish.preview_progress = wish.progress

        self.current_budget = budget
        remaining_budget = budget

        # Проверка на наличие незавершенных желаний
        total_needed = sum(category.total_remaining for category in self.categories)
        if total_needed == 0:
            QMessageBox.information(self, "Информация", "Все желания уже выполнены!")
            return

        # Расчет распределения по категориям
        total_percent = sum(c.percent for c in self.categories if c.uncompleted_preview_wishes)
        if total_percent <= 0:
            QMessageBox.warning(self, "Ошибка", "Нет незавершенных желаний")
            return

        # Первичное распределение по категориям
        category_allocations = {}
        for category in self.categories:
            if not category.uncompleted_preview_wishes:
                continue
            allocation = min(round(budget * (category.percent / total_percent)), category.total_remaining)
            category_allocations[category] = allocation
            category.allocated = allocation

        # Распределение внутри категорий
        for category in self.categories:
            if category not in category_allocations:
                continue
            category_remaining = category_allocations[category]
            if category_remaining <= 0:
                continue

            # Распределение по приоритету (сверху вниз)
            for wish in sorted(category.uncompleted_preview_wishes, key=lambda w: w.position):
                if remaining_budget <= 0 or category_remaining <= 0:
                    break
                to_allocate = min(wish.remaining, category_remaining, remaining_budget)
                if to_allocate > 0:
                    wish.preview_progress += to_allocate
                    category_remaining -= to_allocate
                    remaining_budget -= to_allocate

        # Обновление интерфейса
        self.update_ui(preview=True)
        self.apply_button.setEnabled(True)

        # Отображение информации о распределении
        distribution_info = []
        for category in self.categories:
            if category.allocated > 0:
                distribution_info.append(f"{category.name}: {category.allocated:,.0f}₽")
        if distribution_info:
            self.distribution_label.setText("Распределение: " + " | ".join(distribution_info))
            self.distribution_label.setVisible(True)

        # Отображение нераспределенной суммы
        if remaining_budget > 0:
            self.remaining_label.setText(f"Нераспределённая сумма: {remaining_budget:,.0f}₽")
            self.remaining_label.setVisible(True)
        else:
            self.remaining_label.setVisible(False)
        self.reset_button.setVisible(True)

    def apply_distribution(self):
        """Применение рассчитанного распределения"""
        for category in self.categories:
            for wish in category.wishes:
                wish.progress = wish.preview_progress
        self.update_ui()
        self.save_data()
        self.apply_button.setEnabled(False)
        self.distribution_label.setVisible(False)
        self.remaining_label.setVisible(False)
        self.animate_success()
        self.reset_button.setVisible(False)

    def animate_success(self):
        """Анимация успешного применения"""
        effect = QGraphicsColorizeEffect(self)
        effect.setColor(QColor("#FFD700"))
        self.setGraphicsEffect(effect)

        animation = QPropertyAnimation(effect, b"strength")
        animation.setDuration(1000)
        animation.setStartValue(0.0)
        animation.setKeyValueAt(0.5, 1.0)
        animation.setEndValue(0.0)
        animation.setEasingCurve(QEasingCurve.OutInQuad)
        animation.start()

    def update_ui(self, preview=False):
        """Обновление пользовательского интерфейса"""
        for category in self.categories:
            # Обновление прогресса категории
            total_progress = category.total_preview_progress if preview else category.total_progress
            total_cost = category.total_cost
            category.progress_label.setText(f"{total_progress:,.0f}/{total_cost:,.0f}")
            category.progress_bar.setRange(0, total_cost)
            category.progress_bar.setValue(total_progress)
            category.progress_bar.setStyleSheet(
                self.get_category_progress_style(total_progress, total_cost)
            )

            # Обновление прогресса желаний
            for i in range(category.wish_list.count()):
                item = category.wish_list.item(i)
                if not hasattr(item, 'wish'):
                    continue
                wish = item.wish
                progress = wish.preview_progress if preview else wish.progress
                wish.progress_bar.setRange(0, wish.cost)
                wish.progress_bar.setValue(progress)
                wish.progress_bar.setStyleSheet(
                    self.get_wish_progress_style(progress, wish.cost)
                )
                if wish.cost > 0:
                    percentage = progress / wish.cost * 100
                    wish.progress_bar.setFormat(
                        f"{progress:,.0f}/{wish.cost:,.0f} ({percentage:.1f}%)")
                else:
                    wish.progress_bar.setFormat("0/0 (0%)")

    def apply_styles(self):
        """Применение глобальных стилей"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #F5F5F5;
                font-family: 'Arial';
            }
            QGroupBox {
                background-color: white;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                margin-top: 1ex;
                padding: 10px;
            }
            QLineEdit {
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                padding: 5px;
            }
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #BBDEFB;
            }
            QScrollArea {
                border: none;
            }
        """)

    def load_data(self):
        """Загрузка данных из файла"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.categories = [Category.from_dict(c) for c in data.get('categories', [])]
                    return
            except Exception as e:
                print(f"Ошибка загрузки: {e}")

        # Тестовые данные по умолчанию
        category1 = Category("Электроника", 40)
        category1.add_wish(WishItem("Ноутбук", 15000, 3000))
        category1.add_wish(WishItem("Смартфон", 10000))

        category2 = Category("Одежда", 60)
        category2.add_wish(WishItem("Куртка", 8000))
        category2.add_wish(WishItem("Кроссовки", 5000))

        self.categories = [category1, category2]

    def save_data(self):
        """Сохранение данных в файл"""
        try:
            data = {'categories': [c.to_dict() for c in self.categories]}
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения: {e}")

    def closeEvent(self, event):
        """Обработчик закрытия окна"""
        self.save_data()
        event.accept()


if __name__ == "__main__":
    # Глобальный обработчик исключений
    def exception_hook(exctype, value, traceback):
        error_msg = f"Произошла ошибка:\n\n{value}\n\nПожалуйста, сообщите разработчику."
        QMessageBox.critical(None, "Ошибка", error_msg)
        sys.__excepthook__(exctype, value, traceback)
        sys.exit(1)


    sys.excepthook = exception_hook

    app = QApplication(sys.argv)
    window = WishlistApp()
    window.show()
    sys.exit(app.exec_())