dx = 100
dy = 200

X = 0:dx:10000
Y = 0:dy:10000

Nx = length(X)
Ny = length(Y)

a = zeros(Nx,Ny)

Lx = 20
Ly = 10
for i = 1:1:4
    for j = 1:1:4
        a(Lx*i+1,Ly*j+1) = 1
    end
end

R =3
xc = 10
yc = 10
x = 1:20;
y = 1:20;
[X,Y] = meshgrid(x,y)
circ = sqrt((X-xc).^2+(Y-yc).^2)
circ(xc,yc)=1

idx = find(circ>R)
circ(idx)=0


% idx = find(circ>0)
% circ(idx)=max(circ)


Cfull = conv2(a,circ,'same')



figure(1)
subplot(4,2,1)
imagesc(a)
axis equal
subplot(4,2,2)
imagesc(circ)
axis equal
subplot(4,2,3:8)
imagesc(Cfull)
axis equal

imwrite(Cfull,'TempImage.jpg')





