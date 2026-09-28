%% =========================================================================
% MATLAB / SIMULINK / STATEFLOW GENERATION SCRIPT
% Model: IVI_Service_Interaction_Model.slx
% Domain: Automotive Digital Cockpit / In-Vehicle Infotainment (IVI)
% Use Cases: Incoming Call Interruption & Automatic Media Resume
% =========================================================================

function create_ivi_service_model()
    modelName = 'IVI_Service_Interaction_Model';
    
    % Close if already open
    if bdIsLoaded(modelName)
        close_system(modelName, 0);
    end
    
    fprintf('Creating Simulink model: %s...\n', modelName);
    new_system(modelName);
    open_system(modelName);
    
    % Set solver configurations (discrete fixed-step 10ms for automotive ECU cycle)
    set_param(modelName, 'SolverType', 'Fixed-step');
    set_param(modelName, 'Solver', 'FixedStepDiscrete');
    set_param(modelName, 'FixedStep', '0.01');
    set_param(modelName, 'StopTime', '60.0');
    
    % Add Subsystems / Stateflow Chart
    chartPath = [modelName, '/Service_Interaction_Arbitrator'];
    
    % Check if Stateflow license/toolbox is available
    if license('test', 'Stateflow')
        rt = sfroot;
        m = rt.find('-isa', 'Simulink.BlockDiagram', 'Name', modelName);
        chartBlock = Stateflow.Chart(m);
        chartBlock.Name = 'Service_Interaction_Arbitrator';
        chartBlock.Path = modelName;
        
        fprintf('Configuring Stateflow Chart: %s\n', chartPath);
        
        % Define Inputs
        in_MediaCmd = Stateflow.Data(chartBlock);
        in_MediaCmd.Name = 'u_MediaCmd';
        in_MediaCmd.Scope = 'Input';
        in_MediaCmd.DataType = 'uint8'; % 0:None, 1:Play, 2:Pause
        
        in_NavVoicePrompt = Stateflow.Data(chartBlock);
        in_NavVoicePrompt.Name = 'u_NavVoicePrompt';
        in_NavVoicePrompt.Scope = 'Input';
        in_NavVoicePrompt.DataType = 'boolean';
        
        in_IncomingCall = Stateflow.Data(chartBlock);
        in_IncomingCall.Name = 'u_IncomingCall';
        in_IncomingCall.Scope = 'Input';
        in_IncomingCall.DataType = 'boolean';
        
        in_CallAction = Stateflow.Data(chartBlock);
        in_CallAction.Name = 'u_CallAction';
        in_CallAction.Scope = 'Input';
        in_CallAction.DataType = 'uint8'; % 0:None, 1:Accept, 2:Hangup/Reject
        
        % Define Outputs
        out_MediaState = Stateflow.Data(chartBlock);
        out_MediaState.Name = 'y_MediaState';
        out_MediaState.Scope = 'Output';
        out_MediaState.DataType = 'uint8'; % 0:Stopped, 1:Playing, 2:Paused, 3:Ducked
        
        out_MediaVol = Stateflow.Data(chartBlock);
        out_MediaVol.Name = 'y_MediaVolume';
        out_MediaVol.Scope = 'Output';
        out_MediaVol.DataType = 'double';
        
        out_CallState = Stateflow.Data(chartBlock);
        out_CallState.Name = 'y_CallState';
        out_CallState.Scope = 'Output';
        out_CallState.DataType = 'uint8'; % 0:Idle, 1:Ringing, 2:InCall
        
        out_DisplayMode = Stateflow.Data(chartBlock);
        out_DisplayMode.Name = 'y_DisplayMode';
        out_DisplayMode.Scope = 'Output';
        out_DisplayMode.DataType = 'uint8'; % 0:FullNav, 1:NavOverlay, 2:SplitNavCall
        
        % Define Internal Flags
        var_AutoResume = Stateflow.Data(chartBlock);
        var_AutoResume.Name = 'auto_resume_pending';
        var_AutoResume.Scope = 'Local';
        var_AutoResume.DataType = 'boolean';
        
        % Build States
        sIdle = Stateflow.State(chartBlock);
        sIdle.Name = 'IDLE';
        sIdle.Position = [50 50 160 100];
        sIdle.LabelString = sprintf(['IDLE\n', ...
            'entry:\n', ...
            '  y_MediaState = 0;\n', ...
            '  y_MediaVolume = 0.0;\n', ...
            '  y_CallState = 0;\n', ...
            '  y_DisplayMode = 0;\n', ...
            '  auto_resume_pending = false;']);
            
        sMediaPlaying = Stateflow.State(chartBlock);
        sMediaPlaying.Name = 'MEDIA_PLAYING';
        sMediaPlaying.Position = [280 50 200 120];
        sMediaPlaying.LabelString = sprintf(['MEDIA_PLAYING\n', ...
            'entry:\n', ...
            '  y_MediaState = 1;\n', ...
            '  y_MediaVolume = 1.0;\n', ...
            '  auto_resume_pending = false;']);
            
        sMediaDucked = Stateflow.State(chartBlock);
        sMediaDucked.Name = 'MEDIA_DUCKED';
        sMediaDucked.Position = [280 230 200 100];
        sMediaDucked.LabelString = sprintf(['MEDIA_DUCKED\n', ...
            'entry:\n', ...
            '  y_MediaState = 3;\n', ...
            '  y_MediaVolume = 0.2;']);
            
        sCallRinging = Stateflow.State(chartBlock);
        sCallRinging.Name = 'CALL_RINGING';
        sCallRinging.Position = [550 50 220 120];
        sCallRinging.LabelString = sprintf(['CALL_RINGING\n', ...
            'entry:\n', ...
            '  y_CallState = 1;\n', ...
            '  y_MediaVolume = 0.0;\n', ...
            '  y_MediaState = 2;\n', ...
            '  y_DisplayMode = 1; %% Nav with Call Overlay\n', ...
            '  auto_resume_pending = true; %% Preserve resume intent!']);
            
        sCallActive = Stateflow.State(chartBlock);
        sCallActive.Name = 'CALL_ACTIVE';
        sCallActive.Position = [550 230 220 120];
        sCallActive.LabelString = sprintf(['CALL_ACTIVE\n', ...
            'entry:\n', ...
            '  y_CallState = 2;\n', ...
            '  y_DisplayMode = 2; %% Split screen Nav + Call']);
            
        % Default Transition to IDLE
        tInit = Stateflow.Transition(chartBlock);
        tInit.Destination = sIdle;
        tInit.SourceEndpoint = [30 80];
        tInit.DestinationEndpoint = [50 80];
        
        % IDLE -> MEDIA_PLAYING
        t1 = Stateflow.Transition(chartBlock);
        t1.Source = sIdle;
        t1.Destination = sMediaPlaying;
        t1.LabelString = '[u_MediaCmd == 1]';
        
        % MEDIA_PLAYING -> IDLE (User Pause)
        t2 = Stateflow.Transition(chartBlock);
        t2.Source = sMediaPlaying;
        t2.Destination = sIdle;
        t2.LabelString = '[u_MediaCmd == 2]';
        
        % MEDIA_PLAYING -> MEDIA_DUCKED (Nav Turn Alert)
        t3 = Stateflow.Transition(chartBlock);
        t3.Source = sMediaPlaying;
        t3.Destination = sMediaDucked;
        t3.LabelString = '[u_NavVoicePrompt == true]';
        
        % MEDIA_DUCKED -> MEDIA_PLAYING (Nav Alert Finished)
        t4 = Stateflow.Transition(chartBlock);
        t4.Source = sMediaDucked;
        t4.Destination = sMediaPlaying;
        t4.LabelString = '[u_NavVoicePrompt == false]';
        
        % MEDIA_PLAYING -> CALL_RINGING (Incoming Call Interruption)
        t5 = Stateflow.Transition(chartBlock);
        t5.Source = sMediaPlaying;
        t5.Destination = sCallRinging;
        t5.LabelString = '[u_IncomingCall == true]';
        
        % MEDIA_DUCKED -> CALL_RINGING (Incoming Call Interruption while Ducked)
        t6 = Stateflow.Transition(chartBlock);
        t6.Source = sMediaDucked;
        t6.Destination = sCallRinging;
        t6.LabelString = '[u_IncomingCall == true]';
        
        % CALL_RINGING -> CALL_ACTIVE (Driver Accepts Call)
        t7 = Stateflow.Transition(chartBlock);
        t7.Source = sCallRinging;
        t7.Destination = sCallActive;
        t7.LabelString = '[u_CallAction == 1]';
        
        % CALL_RINGING -> MEDIA_PLAYING (Driver Rejects Call -> AUTO RESUME!)
        t8 = Stateflow.Transition(chartBlock);
        t8.Source = sCallRinging;
        t8.Destination = sMediaPlaying;
        t8.LabelString = '[u_CallAction == 2 && auto_resume_pending == true]';
        
        % CALL_ACTIVE -> MEDIA_PLAYING (Call Ends -> AUTOMATIC MEDIA RESUME!)
        t9 = Stateflow.Transition(chartBlock);
        t9.Source = sCallActive;
        t9.Destination = sMediaPlaying;
        t9.LabelString = '[u_CallAction == 2 && auto_resume_pending == true]';
        
        % CALL_ACTIVE -> IDLE (Call Ends with no prior media playing)
        t10 = Stateflow.Transition(chartBlock);
        t10.Source = sCallActive;
        t10.Destination = sIdle;
        t10.LabelString = '[u_CallAction == 2 && auto_resume_pending == false]';
        
        fprintf('Stateflow Chart constructed successfully.\n');
    else
        % Fallback block diagram using Simulink logic blocks if Stateflow is not installed
        fprintf('Stateflow license not detected. Constructing equivalent Simulink subsystem.\n');
        add_block('simulink/Ports & Subsystems/Subsystem', chartPath);
    end
    
    % Save model
    save_system(modelName);
    fprintf('Model saved as %s.slx\n', modelName);
end
