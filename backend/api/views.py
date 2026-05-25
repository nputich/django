from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from .serializers import UserSerializer, NoteSerializer, OrganizationSerializer
from .models import Note, Organization


#Only logged-in users can see or create their notes
class NoteListCreate(generics.ListCreateAPIView):
    serializer_class = NoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Note.objects.filter(author=user)

    def perform_create(self, serializer):
        if serializer.is_valid():
            serializer.save(author=self.request.user)
        else:
            print(serializer.errors)


#Only logged-in users can delete their own notes
class NoteDelete(generics.DestroyAPIView):
    serializer_class = NoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Note.objects.filter(author=user)


class OrganizationDetail(generics.RetrieveAPIView):
    serializer_class = OrganizationSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    lookup_field = "code"
    lookup_value_regex = r"[\w\-]+"

    def get_queryset(self):
        return Organization.objects.filter(is_active=True)

    def get_object(self):
        code = self.kwargs[self.lookup_field].strip().upper()
        return get_object_or_404(self.get_queryset(), code=code)


#Registration endpoint (open to everyone, no JWT required)
class CreateUserView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]
    authentication_classes = []  #disables JWT checks so registration works