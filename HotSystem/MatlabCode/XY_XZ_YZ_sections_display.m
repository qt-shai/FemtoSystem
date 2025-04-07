function [] = XY_XZ_YZ_sections_display(pathname,filename,minI,maxI)
    % load scan and plot 3 sections, according to cursor
    
    b_close_figure = true;
    b_new_figure = true;
    b_log_scalse = false;
    
    if b_close_figure
        close all;
    end
    
    if b_new_figure
        hf = figure;
    else
        hf = figure(55); % Create figure 55
        hold on
    end
    
    fntsz=16;
    
    if (nargin==0)
        pathname = 'Q:\QT-Quantum_Optic_Lab\expData\scan\';
        [filename, pathname, filterindex] = uigetfile('*.csv','select the scan file',pathname);
    end
    
    T = readtable([pathname filename],'NumHeaderLines',1);
    
    [Nx]=GetN(T{:,5});
    [Nz]=GetN(T{:,7});
    Ny = Nz/Nx;
    % [Ny]=GetN(T{:,6},Nx);
    Nz = length(T{:,7})/Nx/Ny;
    
    if length(T{:,7})/Nx/Ny-round(length(T{:,7})/Nx/Ny)~=0
        error('Nx,Ny,Nz are wrong!')
    end
    
    X_ = linspace(min(T{:,5}),max(T{:,5}),Nx)*1e-6;
    Y_ = linspace(min(T{:,6}),max(T{:,6}),Ny)*1e-6;
    Z_ = linspace(min(T{:,7}),max(T{:,7}),Nz)*1e-6;
    I_=reshape(T{:,4},[Nx,Ny,Nz]);
    
    if nargin<3
        minI = min(I_(:));
        maxI = max(I_(:));
    end
    
    if b_log_scalse
        I_ = log10(I_+eps);
        minI = log10(minI+eps);
        maxI = log10(maxI+eps);
    end
        
    
    set(hf, 'Position', [468, 100, 1317, 1120], 'Name', ['Figure ' num2str(hf.Number)], 'NumberTitle', 'off');
    set(hf, 'Name', filename);
    
    nx_curr=ceil(Nx/2);
    ny_curr=ceil(Ny/2);
    nz_curr=ceil(Nz/2);
    
    hf.UserData=[nx_curr,ny_curr,nz_curr];
    
    % XY
    if Nz>1
        subplot(2,2,1);
    end
    im1=imagesc(X_,Y_,squeeze(I_(:,:,nz_curr)).');
    clim([minI, maxI]);
    axis tight
    set(gca,'ydir','normal');
    if b_log_scalse
        set(gca, 'ColorScale', 'log');
    end
    
    xlabel('x (\mum)');
    ylabel('y (\mum)');
    caption = sprintf('FN = %s\nXY section', filename);
    % caption = sprintf("XY section, FN = " + filename);
    caption = (strrep(caption, '_', '\_'));
    title(caption);
    set(gca,'fontsize',fntsz);
    
    if Nz>1
        hold all
        l11=plot(X_,Y_(ny_curr)*ones(size(X_)),'color',[1 1 1]);
        l12=plot(X_(nx_curr)*ones(size(Y_)),Y_,'color',[1 1 1]);
    end
    
    hcb= colorbar;
    cth = get(hcb,'Title')
    set(cth,'String',"kCounts/sec")
    
    if Nz>1
        % YZ
        subplot(2,2,2);
        im2=imagesc(Z_,Y_,squeeze(I_(nx_curr,:,:)));
        clim([minI, maxI]);
        axis tight
        set(gca,'ydir','normal');
        if b_log_scalse
            set(gca, 'ColorScale', 'log');
        end
    
        xlabel('z (\mum)');
        ylabel('y (\mum)');
        title('ZY section')
        set(gca,'fontsize',fntsz);
    
        hold all
        l21=plot(Z_,Y_(ny_curr)*ones(size(Z_)),'color',[1 1 1]);
        l22=plot(Z_(nz_curr)*ones(size(Y_)),Y_,'color',[1 1 1]);
    
        hcb1= colorbar;
        cth1 = get(hcb1,'Title')
        set(cth1,'String',"kCounts/sec")
    
        % XZ
        subplot(2,2,3);
        im3=imagesc(X_,Z_,squeeze(I_(:,ny_curr,:)).');
        clim([minI, maxI]);
        axis tight
        set(gca,'ydir','normal');
        if b_log_scalse
            set(gca, 'ColorScale', 'log');
        end
    
        xlabel('x (\mum)');
        ylabel('z (\mum)');
        title('XZ section')
        set(gca,'fontsize',fntsz);
    
        hold all
        l31=plot(X_,Z_(nz_curr)*ones(size(X_)),'color',[1 1 1]);
        l32=plot(X_(nx_curr)*ones(size(Z_)),Z_,'color',[1 1 1]);
    
        hcb2= colorbar;
        cth2 = get(hcb2,'Title')
        set(cth2,'String',"kCounts/sec")

        % callback on mouse click
        set(im1,'ButtonDownFcn',{@updateSlices, im1,im2,im3,l11,l12,l21,l22,l31,l32,X_,Y_,Z_,I_,3});
        set(im2,'ButtonDownFcn',{@updateSlices, im1,im2,im3,l11,l12,l21,l22,l31,l32,X_,Y_,Z_,I_,1});
        set(im3,'ButtonDownFcn',{@updateSlices, im1,im2,im3,l11,l12,l21,l22,l31,l32,X_,Y_,Z_,I_,2});

        % Add ROI selection button to the figure
        uicontrol('Style','pushbutton','String','Select ROI', 'Units','normalized','Position',[0.85,0.01,0.05,0.025], 'Callback', ...
            {@selectROI, im1,im2,im3,l11,l12,l21,l22,l31,l32,X_,Y_,Z_,I_,2});
    
    end


end

%% sub-functions
% Function to select a region of interest (ROI) and extract data
function selectROI(~, ~, im1, im2, im3, l11, l12, l21, l22, l31, l32, X_, Y_, Z_, I_, uc_coord)
    % Persistent variable to store the last ROI
    persistent lastROI;

    % ✅ Check if lastROI exists and is valid before deleting
    if ~isempty(lastROI) && isvalid(lastROI)
        delete(lastROI);
    end
    
    % Get the active axes where the user is drawing the ROI
    ax_ = gca;  % Get the current active axes
    roi = drawrectangle(ax_); % Draw an interactive rectangle for selection
    lastROI = roi;
    
    minI = min(I_(:));
    maxI = max(I_(:));

    % Find the parent subplot
    parentAxes = ancestor(roi, 'axes');

    % Determine which subplot was selected
    if parentAxes == im1.Parent
        disp('Selected plot: XY Section');
        selectedPlane = 'XY';
        xyplot = im1.CData;
        xData = im1.XData;
        yData = im1.YData;
        xlable_ = "X [um]"
        ylable_ = "Y [um]"
    elseif parentAxes == im2.Parent
        disp('Selected plot: YZ Section');
        selectedPlane = 'YZ';
        xyplot = im2.CData;
        xData = im2.XData;
        yData = im2.YData;
        xlable_ = "Y [um]"
        ylable_ = "Z [um]"

    elseif parentAxes == im3.Parent
        disp('Selected plot: XZ Section');
        selectedPlane = 'XZ';
        xyplot = im3.CData;
        xData = im3.XData;
        yData = im3.YData;
        xlable_ = "X [um]"
        ylable_ = "Z [um]"

    else
        disp('Unknown selection!');
        delete(roi);
        return;
    end
    
    % Get ROI position (xmin, ymin, width, height)
    roiPos = roi.Position;  

    % Find closest indices for the selected ROI in the image
    [~, xIdx1] = min(abs(xData - roiPos(1)));
    [~, xIdx2] = min(abs(xData - (roiPos(1) + roiPos(3))));
    [~, yIdx1] = min(abs(yData - roiPos(2)));
    [~, yIdx2] = min(abs(yData - (roiPos(2) + roiPos(4))));

    % Ensure correct order
    xIdx = sort([xIdx1, xIdx2]);
    yIdx = sort([yIdx1, yIdx2]);

    % Extract selected 2D matrix
    selectedData = xyplot(yIdx(1):yIdx(2), xIdx(1):xIdx(2));
  
    
    subplot(2,2,4);
    imagesc(xData(xIdx(1):xIdx(2)),yData(yIdx(1):yIdx(2)),selectedData);
    
    hcb= colorbar;
    cth = get(hcb,'Title')
    set(cth,'String',"kCounts/sec")
    
    fontSize = 20;
    title(['Selected Region: ', selectedPlane], 'FontSize', fontSize);
    xlabel(xlable_, 'FontSize', fontSize);
    ylabel(ylable_, 'FontSize', fontSize);

    title(['Selected Region: ', selectedPlane]);
    if (parentAxes == im1.Parent) ||(parentAxes == im2.Parent)
        set(gca,'ydir','normal');
    end
    axis tight
    set(gca,'fontsize',16);
    clim([min(selectedData(:)) max(selectedData(:))])
    
    % Print extracted matrix in Command Window
    disp('Extracted Data:');
    disp(selectedData);

    axes(ax_);

    figure(111)
    subplot(1,2,1);
    imagesc(xData(xIdx(1):xIdx(2)),yData(yIdx(1):yIdx(2)),selectedData);
    
    hcb= colorbar;
    cth = get(hcb,'Title')
    set(cth,'String',"kCounts/sec")

    fontSize = 20;
    title(['Selected Region: ', selectedPlane], 'FontSize', fontSize);
    xlabel(xlable_, 'FontSize', fontSize);
    ylabel(ylable_, 'FontSize', fontSize);
    if (parentAxes == im1.Parent) ||(parentAxes == im2.Parent)
        set(gca,'ydir','normal');
    end
    axis tight
    set(gca,'fontsize',16);
    clim([min(selectedData(:)) max(selectedData(:))])
    
    % Print extracted matrix in Command Window
    disp('Extracted Data:');
    disp(selectedData);
    axes(ax_);
    calcIvsZ(xData(xIdx(1):xIdx(2)),yData(yIdx(1):yIdx(2)),selectedData,ylable_)



    
end

function [N] = GetN(in)
    v = in;
    dv = v(2:end)-v(1:end-1);
    d2v = dv(2:end)-dv(1:end-1);
    if (false)
        figure
        subplot(2,2,1:2)
        plot(v)
        subplot(2,2,3)
        plot(dv)
        subplot(2,2,4)
        plot(d2v)
    end

    N1 = find(round(d2v)>0,1);
    N2 = find(round(d2v)<0,1);
    N = max(N1,N2);
    if (min(dv)==0 && max(dv)==0 && isempty(N)) 
        N = length(v)
    end

end

% mouse click callback function
function updateSlices(src,event,im1,im2,im3,l11,l12,l21,l22,l31,l32,X_,Y_,Z_,I_,uc_coord)
    ax = src.Parent;
    fig = ax.Parent;
    ns=fig.UserData;
    nx=ns(1);
    ny=ns(2);
    nz=ns(3);
    cp=ax.CurrentPoint; % selected point (coordinates)
    
    uc_coord
    switch uc_coord
        case 1
            [tmp,nz]=min(abs(Z_-cp(1,1)));
            [tmp,ny]=min(abs(Y_-cp(1,2)));
        case 2
            [tmp,nx]=min(abs(X_-cp(1,1)));
            [tmp,nz]=min(abs(Z_-cp(1,2)));
        case 3
            [tmp,nx]=min(abs(X_-cp(1,1)));
            [tmp,ny]=min(abs(Y_-cp(1,2)));
    end
    
    fig.UserData=[nx,ny,nz];
    
    % XY
    set(im1,'cdata',squeeze(I_(:,:,nz)).');
    
    set(l11,'ydata',Y_(ny)*ones(size(X_)));
    set(l12,'xdata',X_(nx)*ones(size(Y_)));
    
    
    % YZ
    set(im2,'cdata',squeeze(I_(nx,:,:)));
    
    set(l21,'ydata',Y_(ny)*ones(size(Z_)));
    set(l22,'xdata',Z_(nz)*ones(size(Y_)));
    
    
    % XZ
    set(im3,'cdata',squeeze(I_(:,ny,:)).');
    
    set(l31,'ydata',Z_(nz)*ones(size(X_)));
    set(l32,'xdata',X_(nx)*ones(size(Z_)));
end


function [] = calcIvsZ(x,y,I,yLable_)
    Iz = mean(I,2)
    
    %% close(555)
    figure(111)
    subplot(1,2,2);
    plot(Iz,y,'-*')
    set(gca,'FontSize',20)%, 'FontName', 'Courier')
    fontSize = 20; % Whatever you want.
    caption = sprintf("average intensity vs. depth");
    title(caption, 'FontSize', fontSize);
    if nargin>3
        ylabel(yLable_, 'FontSize', fontSize);
    end
    xlabel('avg I [kcount/sec]', 'FontSize', fontSize);
    axis tight
    grid on
end

