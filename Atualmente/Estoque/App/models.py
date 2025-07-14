from django.db import models
from django.contrib.auth.models import User
from dateutil.relativedelta import relativedelta
from datetime import timedelta, date

class Estoque(models.Model):
    """Representa um local de armazenamento de produtos."""
    nome = models.CharField(max_length=100)
    usuarios = models.ManyToManyField(User, related_name='estoques')

    def __str__(self):
        return self.nome

class Categoria(models.Model):
    """Agrupa produtos em tipos ou classes."""
    nome = models.CharField(max_length=100)
    estoque = models.ForeignKey(Estoque, on_delete=models.CASCADE, related_name='categorias')

    def __str__(self):
        return self.nome

class Metrica(models.Model):
    """Unidade de medida utilizada nos produtos (ex: Litros, Quilos, Unidade)."""
    nome = models.CharField(max_length=100, unique=True)
    codigo = models.CharField(max_length=10, unique=True)
    fixa = models.BooleanField(default=False)

    def __str__(self):
        return self.nome

class Produto(models.Model):
    """Item armazenado no estoque."""
    nome = models.CharField(max_length=100)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True)
    marca = models.CharField(max_length=100, blank=True)
    data_validade = models.DateField(null=True, blank=True)
    preco = models.DecimalField(max_digits=8, decimal_places=2)
    metrica = models.ForeignKey(Metrica, on_delete=models.PROTECT, related_name='produtos')
    estoque = models.ForeignKey(Estoque, on_delete=models.CASCADE, related_name='produtos')
    unidades = models.PositiveIntegerField(default=0)
    data_cadastro = models.DateTimeField(auto_now_add=True)
    data_modificacao = models.DateTimeField(auto_now=True)

    # Cota mínima e controle periódico
    precisa_alerta_cota = models.BooleanField(default=False, help_text="Marque para ativar alerta de cota mínima.")
    cota_minima = models.PositiveIntegerField(default=1, help_text="Quantidade mínima desejada para este produto.")
    checar_periodicamente = models.BooleanField(default=False, help_text="Marque para ativar checagem periódica.")
    INTERVALO_CHOICES = [
        ('dias', 'Dias'),
        ('meses', 'Meses'),
    ]
    intervalo_valor = models.PositiveIntegerField(default=30, blank=True, null=True, help_text="Intervalo entre verificações (ex: 30).")
    intervalo_tipo = models.CharField(max_length=6, choices=INTERVALO_CHOICES, default='dias', blank=True, null=True, help_text="Tipo de intervalo.")

    def __str__(self):
        return self.nome

    def precisa_alerta_cota_func(self):
        """
        Verifica se o produto está abaixo da cota mínima e se o alerta está ativo.
        Retorna True se precisa exibir alerta de cota mínima.
        """
        if not self.precisa_alerta_cota or not self.cota_minima or self.cota_minima <= 0:
            return False
        return self.unidades < self.cota_minima

    def proxima_verificacao(self, ultima_verificacao):
        """
        Calcula a próxima data de verificação a partir da última, se o intervalo está configurado.
        """
        if not self.checar_periodicamente or not self.intervalo_valor:
            return None
        if self.intervalo_tipo == 'dias':
            return ultima_verificacao + timedelta(days=self.intervalo_valor)
        elif self.intervalo_tipo == 'meses':
            return ultima_verificacao + relativedelta(months=self.intervalo_valor)
        return None

class Movimentacao(models.Model):
    """Registra movimentações de produtos (entrada ou saída)."""
    ENTRADA = 'E'
    SAIDA = 'S'
    TIPO_CHOICES = [
        (ENTRADA, 'Entrada'),
        (SAIDA, 'Saída'),
    ]
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=1, choices=TIPO_CHOICES)
    quantidade = models.PositiveIntegerField()
    data = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.produto.nome} ({self.quantidade})"