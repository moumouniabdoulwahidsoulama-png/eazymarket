from django.contrib import admin

from .models import Category, Favorite, Product, ProductImage, ProductReview


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "order")
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("order",)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "seller", "category", "base_price", "stock", "is_available", "is_approved")
    list_filter = ("is_approved", "is_available", "is_featured", "condition", "category")
    search_fields = ("name", "description", "seller__username")
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("is_approved", "is_available")
    inlines = (ProductImageInline,)
    readonly_fields = ("views_count", "sold_count", "rating", "num_reviews")


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "rating", "created_at")
    list_filter = ("rating",)


admin.site.register(Favorite)
