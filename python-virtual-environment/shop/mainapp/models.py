import sys
from PIL import Image
from io import BytesIO
from django.db import models
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.utils import timezone

User = get_user_model()

class Category(models.Model):
	
	name = models.CharField(max_length=255, verbose_name='Имя категории')
	slug = models.SlugField(unique=True)

	def __str__(self):
		return self.name
	
	def get_absolute_url(self):
		return reverse('category_detail', kwargs={'slug': self.slug})
	
	def get_fields_for_filter_in_template(self):
		return ProductFeatures.objects.filter(
			category=self,
			use_in_filter=True
		).prefetch_related('category').value('feature_key', 'feature_measure', 'feature_name', 'filter_type')


class Product(models.Model):

	category = models.ForeignKey(Category, verbose_name='Категория', on_delete=models.CASCADE)
	title = models.CharField(max_length=255, verbose_name='Наименование')
	slug = models.SlugField(unique=True)
	image =models.ImageField(verbose_name='Изображение')
	description = models.TextField(verbose_name='Описание', default=True)
	price = models.DecimalField(max_digits=9, decimal_places=0, verbose_name='Цена')
	features = models.ManyToManyField("specs.ProductFeatures", blank=True, related_name='features_for_product')

	def __str__(self):
		return self.title
	
	def save(self, *args, **kwargs):
		
		image = self.image
		img = Image.open(image)
		new_img = img.convert('RGB')
		resized_img = new_img.resize((300, 300), Image.ANTIALIAS)
		filestream = BytesIO()
		resized_img.save(filestream, 'JPEG', quality=90)
		filestream.seek(0)
		name = '{}.{}'.format(*self.image.name.split('.'))
		self.image = InMemoryUploadedFile(filestream, 'ImageField', name, 'jpeg/image', sys.getsizeof(filestream), None)
		super().save(*args, **kwargs)

	def get_model_name(self):
		return self.__class__.__name__.lower()
	
	def get_absolute_url(self):
		return reverse('product_detail', kwargs={'slug': self.slug})
	
	def get_features(self):
		return {f.feature.feature_name: ' '.join([f.value, f.feature.unit or ""]) for f in self.features.all()}
	
	
class ProductFeatures(models.Model):
	
	RADIO = 'radio'
	CHECKBOX = 'checkbox'
	
	FILTER_TYPE_CHOICES = (
		(RADIO, 'Радиокнопка'),
		(CHECKBOX, 'Чекбокс')
	)
	
	feature_key = models.CharField(max_length=100, verbose_name='Ключ характеристики')
	feature_name = models.CharField(max_length=255, verbose_name='Наименование характеристики')
	category = models.ForeignKey(Category, verbose_name='Категория', on_delete=models.CASCADE)
	postfix_for_value = models.CharField(
		max_length=20,
		null=True,
		blank=True,
		verbose_name='Постфикс для значения'
	)
	use_in_filter = models.BooleanField(default=False, verbose_name='Использовать в фильтрации товара')
	filter_type = models.CharField(
		max_length=20,
		verbose_name='Тип фильтра',
		default=CHECKBOX,
		choices=FILTER_TYPE_CHOICES
	)
	filter_measure = models.CharField(
		max_length=50,
		verbose_name='Единица измерения для фильтра'
	)
	
	def __str__(self):
		return f'Категория - "{self.category.name}" | Характеристика - "{self.feature_name}"'
	

class ProductFeatureValidator(models.Model):

	category = models.ForeignKey(Category, verbose_name='Категория', on_delete=models.CASCADE)
	feature = models.ForeignKey(ProductFeatures, verbose_name='Характеристика', null=True, blank=True, on_delete=models.CASCADE)
	feature_value =models.CharField(
		max_length=255,
		unique=True,
		null=True,
		blank=True,
		verbose_name='Значение характеристики'
	)
	
	def __str__(self):
		if not self.feature:
			return f'Валидатор категории "{self.category.name}" - характеристика не выбрана!'
		return f'Валидатор категории "{self.category.name}" |  '\
			   f'Характеристика "{self.feature.feature_name}" | '\
			   f'Значение "{self.feature_value}"'


class CartProduct(models.Model):

	user = models.ForeignKey('Customer', verbose_name='Пользователь', on_delete=models.CASCADE)
	cart = models.ForeignKey('Cart', verbose_name='Корзина', on_delete=models.CASCADE, related_name='related_products')
	product = models.ForeignKey(Product, verbose_name='Товар', on_delete=models.CASCADE)
	qty = models.PositiveIntegerField(default=1)
	final_price = models.DecimalField(max_digits=9, decimal_places=0, verbose_name='Общая стоимость')

	def __str__(self):
		return "Продукт: {} (для корзины)".format(self.product.title)

	def save(self, *args, **kwargs):
		self.final_price = self.qty * self.product.price
		super().save(*args, **kwargs)
		


class Cart(models.Model):

	owner = models.ForeignKey('Customer', null=True, verbose_name='Владелец', on_delete=models.CASCADE)
	products = models.ManyToManyField(CartProduct, blank=True, related_name='related_cart')
	total_products = models.PositiveIntegerField(default=0)
	final_price = models.DecimalField(max_digits=9, decimal_places=0, default=0, verbose_name='Общая стоимость')
	in_order = models.BooleanField(default=False)
	for_anonymous_user = models.BooleanField(default=False)

	def __str__(self):
		return str(self.id)
	
	
class Customer(models.Model):

	user =models.ForeignKey(User, verbose_name='Пользователь', on_delete=models.CASCADE)
	phone = models.CharField(max_length=20, verbose_name='Номер телефона', null=True, blank=True)
	address = models.CharField(max_length=255, verbose_name='Адрес', null=True, blank=True)
	orders = models.ManyToManyField('Order', blank=True, verbose_name='Заказы покупателя', related_name='related_customer')
	
	def __str__(self):
		return "Покупатель: {} {}".format(self.user.first_name, self.user.last_name)
	
	
	
class Order(models.Model):

	STATUS_NEW = 'new'
	STATUS_IN_PROGRESS = 'in_progress'
	STATUS_READY = 'is_ready'
	STATUS_COMPLETED = 'completed'
	STATUS_PAYED = 'payes'

	BUYING_TYPE_SELF = 'self'
	BUYING_TYPE_DELIVERY = 'delivery'

	STATUS_CHOICES = (
		(STATUS_PAYED, "Заказ оплачен"),
		(STATUS_NEW, 'Новый заказ'),
		(STATUS_IN_PROGRESS, 'Заказ в обработке'),
		(STATUS_READY, 'Заказ готов'),
		(STATUS_COMPLETED, 'Заказ выполнен')
	)

	BUYING_TYPE_CHOICES = (
		(BUYING_TYPE_SELF, 'Самовывоз'),
		(BUYING_TYPE_DELIVERY, 'Доставка')
	)

	customer = models.ForeignKey(Customer, verbose_name='Покупатель', related_name='related_orders', on_delete=models.CASCADE)
	first_name = models.CharField(max_length=255, verbose_name='Имя')
	last_name = models.CharField(max_length=255, verbose_name='Фамилия')
	phone = models.CharField(max_length=20, verbose_name='Телефон')
	cart = models.ForeignKey(Cart, verbose_name='Корзина', on_delete=models.CASCADE, null=True, blank=True)
	address = models.CharField(max_length=1024, verbose_name='Адрес', null=True, blank=True)
	status = models.CharField(
		max_length=100,
		verbose_name='Статус заказ',
		choices=STATUS_CHOICES,
		default=STATUS_NEW
	)
	buying_type = models.CharField(
		max_length=100,
		verbose_name='Тип заказа',
		choices=BUYING_TYPE_CHOICES,
		default=BUYING_TYPE_SELF
	)
	comment = models.TextField(verbose_name='Комментарий к заказу', null=True, blank=True)
	created_at = models.DateTimeField(auto_now=True, verbose_name='Дата создания заказа')
	order_date = models.DateField(verbose_name='Дата получения заказа', default=timezone.now)

	def __str__(self):
		return str(self.id)
