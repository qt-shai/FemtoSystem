clc
clear all
if exist('lastFolder.mat', 'file')
    load('lastFolder.mat', 'filePath');
    if ~ischar(filePath) && ~isstring(filePath)
        disp('filePath is empty.');
        filePath = pwd;
    elseif ~exist(filePath, 'dir')
        disp('filePath does not exist. loading default.');
        filePath = pwd;
    end
else
    filePath = pwd;  % Default to current directory
end
current_path = pwd;
cd(filePath);
[fileNames, filePath] = uigetfile('*.csv', 'Select Files', 'MultiSelect', 'on');
cd(current_path);

save('lastFolder.mat', 'filePath');
% Handle single file selection
if ischar(fileNames)
    fileNames = {fileNames};  % Convert to cell array
end

if iscell(fileNames)
    for i = 1:length(fileNames)
        fn = fullfile(filePath, fileNames{i});
        XY_XZ_YZ_sections_display(filePath, fileNames{i});  % Run the test function with pathname and filename
        disp(fprintf('%s\n', fn));  % Print fn with a newline
    end
else
    disp('No files selected.');
end



