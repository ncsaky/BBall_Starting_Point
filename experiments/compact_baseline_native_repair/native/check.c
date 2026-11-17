/* Bounded standalone ABI/buffer harness; optional UBSan, never a release claim. */
#include <assert.h>
#include <stdio.h>
#include "geometry.c"
int main(void){
    double p[NIN]={0};p[RX]=3;p[RY]=7.4;p[DX]=2;p[DY]=6;p[H0]=1.5;p[VX]=1;p[VY]=2;p[STAND]=2.8;p[JUMP]=.7;p[SPAN]=.65;p[ACC]=3;p[SPEED]=5;p[DSTAND]=3;p[DJUMP]=.8;p[DSPAN]=.7;p[DACC]=3;p[DSPEED]=5;p[DREACTION]=.2;p[REACTION]=.14;p[HORIZON]=.65;p[VZ]=-1;p[GRAVITY]=9.81;p[MINZ]=.2;p[GATHER]=.18;p[TAKEOFF]=.12;p[HALFWIDTH]=7.5;p[BACKY]=-1.5;p[FRONTY]=12.5;p[STEPS]=16;p[BISECTS]=10;
    const double axes[18]={0,1,0,0,-1,0,-1,0,0,1,0,0,0,0,1,0,0,-1};for(int i=0;i<18;i++)p[AXES+i]=axes[i];
    double guarded[NOUT+2],e;int32_t d;
    for(int i=0;i<512;i++){
        e=(double)i/100;d=i%6;guarded[0]=12345;guarded[NOUT+1]=54321;
        int rc=compact_geometry_batch(p,NIN,3,7.4,&e,&d,1,guarded+1,NOUT);assert(rc==0);assert(guarded[0]==12345&&guarded[NOUT+1]==54321);
        int status=(int)guarded[1];assert(status>=0&&status<=5);if(status!=5)assert(isfinite(guarded[2]));
    }
    double output[NOUT];for(int i=0;i<NOUT;i++)output[i]=777;e=.9;d=1;
    assert(compact_geometry_batch(p,NIN-1,3,7.4,&e,&d,1,output,NOUT)<0);
    assert(compact_geometry_batch(p,NIN,3,7.4,&e,&d,405,output,NOUT)<0);
    assert(compact_geometry_batch(p,NIN,3,7.4,&e,&d,1,output,NOUT-1)<0);
    d=6;assert(compact_geometry_batch(p,NIN,3,7.4,&e,&d,1,output,NOUT)<0);d=1;
    e=NAN;assert(compact_geometry_batch(p,NIN,3,7.4,&e,&d,1,output,NOUT)<0);e=.9;
    p[ACC]=0;assert(compact_geometry_batch(p,NIN,3,7.4,&e,&d,1,output,NOUT)<0);p[ACC]=3;
    assert(compact_geometry_batch(NULL,NIN,3,7.4,&e,&d,1,output,NOUT)<0);
    for(int i=0;i<NOUT;i++)assert(output[i]==777);
    puts("PASS:512 valid numeric rows,canaries,and7 invalid ABI/size/type-value guards");return 0;
}
