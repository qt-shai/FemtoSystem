function [] = ParsePLotScan()
% load scan and plot
close all
clear
clc

pathname = 'Q:\QT-Quantum_Optic_Lab\expData\scan\';
filename = '2024_6_13_8_33_45scan.csv';
[filename, pathname, filterindex] = uigetfile('*.csv','select the scan file',pathname);
T = readtable([pathname filename],'NumHeaderLines',1);

[X_,Nx]=GetAxisParameters(T{:,5});
[Y_,Ny]=GetAxisParameters(T{:,6});
[Z_,Nz]=GetAxisParameters(T{:,7});

% example to verify coordinates
% A = [1 2 3 4 5; 1 2 3 4 5; 1 2 3 4 5]
% B = A'
% B = B(:)
% C = reshape(B,5,3)'
I_=reshape(T{:,4},[Nx,Ny,Nz]);
Ix_ = round(reshape(T{:,1},[Nx,Ny,Nz])/1e4)*10;
Iy_ = round(reshape(T{:,2},[Nx,Ny,Nz])/1e4)*10;
Iz_ = round(reshape(T{:,3},[Nx,Ny,Nz])/1e4)*10;

% plot results
for i = 1:Nz
    idx_z = i;
    I = I_(:,:,idx_z)';
    Ix = Ix_(:,:,idx_z)';
    Iy = Iy_(:,:,idx_z)';
    
    X = Ix';
    X = X(:);
    Y = Iy';
    Y = Y(:);
    Z = I';
    Z = Z(:);
    
    subplot_handles = gobjects(2, 2); 
    figure(i)
    
    % subplot_handles(1,1) = subplot(3,3,1)
    % plot3(X./1e3,Y./1e3,Z./1e3)
    % set(subplot_handles(1,1), 'YDir', 'normal');
    % grid on
    % xlabel(subplot_handles(1, 1), 'X [um]')
    % ylabel(subplot_handles(1, 1), 'Y [um]')
    % 
    % subplot_handles(1,2) = subplot(3,3,[4:5,8:9])
    subplot_handles(1,2) = subplot(1,1,1);
    imagesc(X_./1e3,Y_./1e3,I);
    xtickformat(subplot_handles(1,2),'%.3f')
    ytickformat(subplot_handles(1,2),'%.3f')
    set(subplot_handles(1,2), 'YDir', 'normal');
    axis equal
    
    maxI = max(I_(:))
    if (max(I_(:))==0)
        maxI = 25
    end

    caxis(subplot_handles(1,2),[0, maxI]);
    colorbar
    title(subplot_handles(1,2),['z = ' num2str(Z_(i))])
    xlabel(subplot_handles(1, 2), 'X [um]')
    ylabel(subplot_handles(1, 2), 'Y [um]')
    
end

end

function [v_, N] = GetAxisParameters(in)
    % v = round(in/1e3)*1e3;
    v = in;
    dv = v(2:end)-v(1:end-1);
    idx = find(dv>10);
    dv = median(dv(idx));
    v_ = [round(v(1)/1e3)*1e3:dv:round(v(end)/1e3)*1e3];
    N = length(v_);
end


